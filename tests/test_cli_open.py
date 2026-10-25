import json

import pytest

from dogear.cli import Context, main
from tests.fakes import make_claude_session

ID = "8f1c2a3b-0000-4000-8000-000000000001"


@pytest.fixture
def saved(homes):
    cwd = homes.root / "My Project" / "é"
    cwd.mkdir(parents=True)
    make_claude_session(homes.claude, ID, cwd, ai_title="Jobs")
    homes.dogear.mkdir()
    fav = {"agent": "claude", "session_id": ID, "cwd": str(cwd), "label": "jobs", "title": "Jobs", "note": "", "tags": [], "args": "--model opus", "added_at": "2026-01-01T00:00:00Z"}
    (homes.dogear / "favorites.json").write_text(json.dumps({"version": 1, "favorites": [fav]}), encoding="utf-8")
    homes.cwd = cwd
    return homes


def run(argv, **kw):
    ctx = Context.for_test(**kw)
    return main(argv, ctx), ctx


def test_open_execs_resume_in_cwd(saved):
    code, ctx = run(["open", "jobs"])
    assert code == 0, ctx.stderr.getvalue()
    [(cmd, cwd)] = ctx.exec_calls
    assert cmd == ["/fake/bin/claude", "--model", "opus", "--resume", ID]
    assert cwd == str(saved.cwd)
    err = ctx.stderr.getvalue().strip().splitlines()
    assert len(err) == 1 and "--resume" in err[0] and "claude" in err[0]


def test_open_by_number(saved):
    assert run(["open", "1"])[0] == 0


def test_open_extra_flags_replace(saved):
    _, ctx = run(["open", "jobs", "--", "--model", "x"])
    assert ctx.exec_calls[0][0] == ["/fake/bin/claude", "--model", "x", "--resume", ID]


def test_open_bare_double_dash_means_no_flags(saved):
    _, ctx = run(["open", "jobs", "--"])
    assert ctx.exec_calls[0][0] == ["/fake/bin/claude", "--resume", ID]


def test_open_missing_session(saved):
    next((saved.claude / "projects").glob(f"*/{ID}.jsonl")).unlink()
    code, ctx = run(["open", "jobs"])
    assert code == 1 and "prune" in ctx.stderr.getvalue() and ctx.exec_calls == []


def test_open_missing_folder(saved):
    saved.cwd.rmdir()
    code, ctx = run(["open", "jobs"])
    assert code == 1 and "folder" in ctx.stderr.getvalue() and ctx.exec_calls == []


def test_open_command_not_found(saved):
    code, ctx = run(["open", "jobs"], which=lambda n: None)
    assert code == 1 and "[claude] command" in ctx.stderr.getvalue()


def test_open_unknown_ref(saved):
    assert run(["open", "nope"])[0] == 1


def test_bare_dogear_picks_and_opens(saved):
    code, ctx = run([], stdin="1\n", stdin_isatty=True, which=lambda n: None if n == "fzf" else f"/fake/bin/{n}")
    assert code == 0, ctx.stderr.getvalue()
    assert ctx.exec_calls[0][0][-2:] == ["--resume", ID]


def test_bare_dogear_cancel(saved):
    code, ctx = run([], stdin="\n", stdin_isatty=True, which=lambda n: None)
    assert code == 0 and ctx.exec_calls == []


def test_bare_dogear_without_tty(saved):
    code, ctx = run([])
    assert code == 1 and "TTY" in ctx.stderr.getvalue()


def test_bare_dogear_empty(homes):
    code, ctx = run([], stdin_isatty=True)
    assert code == 0 and "dogear add" in ctx.stdout.getvalue()
