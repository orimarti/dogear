import json

import pytest

from dogear.cli import Context, main
from tests.fakes import make_claude_session, make_codex_rollout

IDS = [f"aaaa000{i}-0000-4000-8000-00000000000{i}" for i in range(1, 4)]
CX = "cccc0001-0000-4000-8000-00000000000c"


def run(argv, **kw):
    ctx = Context.for_test(**kw)
    return main(argv, ctx), ctx


@pytest.fixture
def three(homes):
    """todo (oldest, tag work), docs (tag work), misc (codex, newest)."""
    make_claude_session(homes.claude, IDS[0], homes.root / "a", ai_title="Todo")
    make_claude_session(homes.claude, IDS[1], homes.root / "b", ai_title="Docs")
    make_codex_rollout(homes.codex, CX, homes.root / "c")
    homes.dogear.mkdir()
    data = {
        "version": 1,
        "favorites": [
            {"agent": "claude", "session_id": IDS[0], "cwd": str(homes.root / "a"), "label": "todo", "title": "Todo", "note": "n", "tags": ["work"], "args": "", "added_at": "2026-01-01T00:00:00Z", "future": 1},
            {"agent": "claude", "session_id": IDS[1], "cwd": str(homes.root / "b"), "label": "docs", "title": "Docs", "note": "", "tags": ["work"], "args": "", "added_at": "2026-01-02T00:00:00Z"},
            {"agent": "codex", "session_id": CX, "cwd": str(homes.root / "c"), "label": "misc", "title": "Misc", "note": "", "tags": [], "args": "", "added_at": "2026-01-03T00:00:00Z"},
        ],
    }
    (homes.dogear / "favorites.json").write_text(json.dumps(data), encoding="utf-8")
    return homes


def favs(homes):
    return {f["label"]: f for f in json.loads((homes.dogear / "favorites.json").read_text(encoding="utf-8"))["favorites"]}


def table_labels(out):
    return [line.split()[1] for line in out.splitlines()[1:]]


def test_ls_empty(homes):
    code, ctx = run(["ls"])
    assert code == 0 and "no favourites yet" in ctx.stdout.getvalue()


def test_ls_newest_first(three):
    code, ctx = run(["ls"])
    assert code == 0
    assert table_labels(ctx.stdout.getvalue()) == ["misc", "docs", "todo"]


def test_ls_filters_keep_numbers(three):
    out = run(["ls", "-t", "work"])[1].stdout.getvalue()
    rows = out.splitlines()[1:]
    assert [r.split()[:2] for r in rows] == [["2", "docs"], ["3", "todo"]]
    assert table_labels(run(["ls", "--agent", "codex"])[1].stdout.getvalue()) == ["misc"]


def test_ls_json(three):
    out = json.loads(run(["ls", "--json"])[1].stdout.getvalue())
    assert [f["label"] for f in out] == ["misc", "docs", "todo"]
    assert out[2]["future"] == 1


def test_ls_marks_missing(three):
    next((three.claude / "projects").glob(f"*/{IDS[1]}.jsonl")).unlink()
    out = run(["ls"])[1].stdout.getvalue()
    assert "docs (missing)" in out and "todo (missing)" not in out


def test_rename(three):
    assert run(["rename", "1", "newname"])[0] == 0
    assert "newname" in favs(three) and "misc" not in favs(three)


def test_rename_clash(three):
    code, ctx = run(["rename", "todo", "docs"])
    assert code == 1 and "already" in ctx.stderr.getvalue()


def test_rename_unknown(three):
    code, ctx = run(["rename", "99", "x"])
    assert code == 1 and "no favourite '99'" in ctx.stderr.getvalue()


def test_note_set_and_clear(three):
    run(["note", "docs", "hello"])
    assert favs(three)["docs"]["note"] == "hello"
    run(["note", "todo", ""])
    assert favs(three)["todo"]["note"] == ""


def test_tag_changes(three):
    code, ctx = run(["tag", "todo", "+a", "b", "-work"])
    assert code == 0, ctx.stderr.getvalue()
    assert favs(three)["todo"]["tags"] == ["a", "b"]


def test_edit_args(three):
    code, _ = run(["edit", "todo", "--args", "--model opus"])
    assert code == 0 and favs(three)["todo"]["args"] == "--model opus"
    run(["edit", "todo", "--args="])
    assert favs(three)["todo"]["args"] == ""


def test_rm_uses_original_numbers(three):
    code, _ = run(["rm", "1", "2"])
    assert code == 0 and list(favs(three)) == ["todo"]


def test_rm_unknown_removes_nothing(three):
    assert run(["rm", "todo", "nope"])[0] == 1
    assert len(favs(three)) == 3


def test_prune_yes(three):
    next((three.claude / "projects").glob(f"*/{IDS[0]}.jsonl")).unlink()
    code, ctx = run(["prune", "--yes"])
    assert code == 0 and set(favs(three)) == {"docs", "misc"}
    assert "todo" in ctx.stdout.getvalue()


def test_prune_asks(three):
    next((three.claude / "projects").glob(f"*/{IDS[0]}.jsonl")).unlink()
    assert run(["prune"], stdin="n\n", stdin_isatty=True)[0] == 0
    assert len(favs(three)) == 3
    assert run(["prune"], stdin="y\n", stdin_isatty=True)[0] == 0
    assert "todo" not in favs(three)


def test_prune_without_tty(three):
    next((three.claude / "projects").glob(f"*/{IDS[0]}.jsonl")).unlink()
    code, ctx = run(["prune"])
    assert code == 1 and "--yes" in ctx.stderr.getvalue()


def test_prune_nothing(three):
    code, ctx = run(["prune"])
    assert code == 0 and "nothing to prune" in ctx.stdout.getvalue()


def test_config_path(homes):
    code, ctx = run(["config", "--path"])
    assert code == 0 and ctx.stdout.getvalue().strip() == str(homes.dogear / "config.toml")


def test_config_show(homes):
    out = run(["config"])[1].stdout.getvalue()
    assert 'command = "claude"' in out and 'use_fzf = "auto"' in out
