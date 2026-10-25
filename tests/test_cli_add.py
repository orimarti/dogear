import json

import pytest

from dogear.cli import Context, main
from tests.fakes import FakeProcessTable, make_claude_session, make_codex_rollout, write_claude_live, append_codex_index

A = "8f1c2a3b-0000-4000-8000-000000000001"
B = "8f1c2a3b-1111-4000-8000-000000000002"
X = "ab12cd34-0000-4000-8000-00000000000a"


def favs(homes):
    return json.loads((homes.dogear / "favorites.json").read_text(encoding="utf-8"))["favorites"]


def run(argv, **kw):
    ctx = Context.for_test(**kw)
    code = main(argv, ctx)
    return code, ctx


def in_claude(homes, sid):
    write_claude_live(homes.claude, 100, sid, homes.root / "p")
    return FakeProcessTable({300: {"ppid": 200, "cmd": "python3"}, 200: {"ppid": 100, "cmd": "/bin/zsh"}, 100: {"ppid": 1, "cmd": "claude"}})


def outside(homes):
    return FakeProcessTable({300: {"ppid": 200, "cmd": "python3"}, 200: {"ppid": 1, "cmd": "/bin/zsh"}})


def test_add_explicit_id(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="New jobs API")
    code, ctx = run(["add", A])
    assert code == 0
    [f] = favs(homes)
    assert f["label"] == "new-jobs-api" and f["session_id"] == A and f["agent"] == "claude"
    assert f["added_at"] == "2026-01-02T03:04:05Z" and f["cwd"] == str(homes.root / "p")
    assert "saved new-jobs-api" in ctx.stdout.getvalue()


def test_add_prefix(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="T")
    assert run(["add", A[:10]])[0] == 0
    assert favs(homes)[0]["session_id"] == A


def test_add_ambiguous_prefix_across_agents(homes):
    make_claude_session(homes.claude, "ab12cd34-9999-4000-8000-000000000001", homes.root / "p", ai_title="Claude one")
    make_codex_rollout(homes.codex, X, homes.root / "q")
    code, ctx = run(["add", "ab12cd34"])
    assert code == 1
    err = ctx.stderr.getvalue()
    assert X in err and "ab12cd34-9999" in err and "claude" in err and "codex" in err
    assert not (homes.dogear / "favorites.json").exists()
    assert run(["add", "ab12cd34", "--agent", "codex"])[0] == 0
    assert favs(homes)[0]["agent"] == "codex"


def test_add_unknown_id(homes):
    code, ctx = run(["add", "deadbeef"])
    assert code == 1 and "no session matches" in ctx.stderr.getvalue()


def test_add_current_with_label_token(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="T")
    code, ctx = run(["add", "my-label", "-t", "work"], proc_table=in_claude(homes, A), pid=300)
    assert code == 0, ctx.stderr.getvalue()
    [f] = favs(homes)
    assert f["label"] == "my-label" and f["session_id"] == A and f["tags"] == ["work"]


def test_add_falls_back_to_picker(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="Older", mtime=1_000_000)
    make_codex_rollout(homes.codex, X, homes.root / "q", mtime=2_000_000)
    append_codex_index(homes.codex, X, "Newest")
    code, ctx = run(["add"], proc_table=outside(homes), pid=300, stdin="1\n", stdin_isatty=True, which=lambda n: None)
    assert code == 0, ctx.stderr.getvalue()
    assert favs(homes)[0]["session_id"] == X


def test_add_detection_fails_without_tty(homes):
    # inside claude, but no sessions/<pid>.json to say which session
    table = FakeProcessTable({300: {"ppid": 100, "cmd": "py"}, 100: {"ppid": 1, "cmd": "claude"}})
    code, ctx = run(["add"], proc_table=table, pid=300)
    assert code == 1
    assert "dogear add <session-id>" in ctx.stderr.getvalue()


def test_add_outside_agent_without_tty(homes):
    code, ctx = run(["add"], proc_table=outside(homes), pid=300)
    assert code == 1 and "dogear add <session-id>" in ctx.stderr.getvalue()


def test_add_twice_no_duplicate(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="T")
    run(["add", A])
    code, ctx = run(["add", A, "-n", "remember this"])
    assert code == 0
    assert "already saved as t" in ctx.stdout.getvalue()
    [f] = favs(homes)
    assert f["note"] == "remember this"


def test_add_label_clash_suffix(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="Same")
    make_claude_session(homes.claude, B, homes.root / "q", ai_title="Same")
    run(["add", A])
    run(["add", B])
    assert sorted(f["label"] for f in favs(homes)) == ["same", "same-2"]


def test_add_numeric_label_rejected(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    code, ctx = run(["add", A, "-l", "123"])
    assert code == 1 and "digits" in ctx.stderr.getvalue()


@pytest.mark.parametrize("argv,expected", [(["--args", "--model opus"], "--model opus"), (["--args=--verbose"], "--verbose")])
def test_add_args_verbatim(homes, argv, expected):
    make_claude_session(homes.claude, A, homes.root / "p")
    code, ctx = run(["add", A, *argv])
    assert code == 0, ctx.stderr.getvalue()
    assert favs(homes)[0]["args"] == expected


def test_add_unicode_paths_and_titles(homes):
    cwd = homes.root / "My Project" / "é"
    make_claude_session(homes.claude, A, cwd, ai_title="Café — résumé")
    assert run(["add", A])[0] == 0
    [f] = favs(homes)
    assert f["label"] == "cafe-resume" and f["cwd"] == str(cwd) and f["title"] == "Café — résumé"


def test_add_tags_normalised(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    run(["add", A, "-t", "work", "-t", " work ", "-t", "", "-t", "client"])
    assert favs(homes)[0]["tags"] == ["work", "client"]
