"""Regression tests for the minor findings deferred from the v1 review."""

import io
import json
import os
import sys
import time
import unicodedata

import pytest

from dogear import picker as picker_mod
from dogear import store
from dogear.agents.claude import ClaudeAdapter
from dogear.cli import Context, main
from dogear.errors import DogearError
from dogear.favorites import validate_label
from dogear.render import format_table
from tests.fakes import FakeProcessTable, make_claude_session, make_codex_rollout, write_claude_live

A = "8f1c2a3b-0000-4000-8000-000000000001"
X = "ab12cd34-0000-4000-8000-00000000000a"


def run(argv, **kw):
    ctx = Context.for_test(**kw)
    return main(argv, ctx), ctx


def favs(homes):
    return json.loads((homes.dogear / "favorites.json").read_text(encoding="utf-8"))["favorites"]


def in_claude(homes, sid):
    write_claude_live(homes.claude, 100, sid, homes.root / "p")
    return FakeProcessTable({300: {"ppid": 100, "cmd": "python3"}, 100: {"ppid": 1, "cmd": "claude"}})


def outside():
    return FakeProcessTable({300: {"ppid": 1, "cmd": "python3"}})


# 1 ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["-x", "--model"])
def test_label_cannot_start_with_dash(bad):
    with pytest.raises(DogearError, match="-"):
        validate_label(bad)


# 2 ---------------------------------------------------------------------------


def test_uppercase_prefix_matches(homes):
    make_codex_rollout(homes.codex, X, homes.root / "q")
    make_claude_session(homes.claude, A, homes.root / "p")
    assert run(["add", X[:8].upper(), "--agent", "codex"])[0] == 0
    assert run(["add", A.upper()])[0] == 0
    assert {f["session_id"] for f in favs(homes)} == {A, X}


# 3 ---------------------------------------------------------------------------


def test_bad_label_rejected_before_picker(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    code, ctx = run(["add", "-l", "my label"], proc_table=outside(), pid=300, stdin="1\n", stdin_isatty=True, which=lambda n: None)
    assert code == 1 and "invalid label" in ctx.stderr.getvalue()
    assert "  1  " not in ctx.stderr.getvalue()  # no picker was shown
    assert ctx.stdin.read() == "1\n"


# 4 ---------------------------------------------------------------------------


def test_label_for_saved_session_renames(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="T")
    run(["add", A])
    code, ctx = run(["add", A, "-l", "newname"])
    assert code == 0 and "renamed to newname" in ctx.stdout.getvalue()
    assert [f["label"] for f in favs(homes)] == ["newname"]
    code, ctx = run(["add", "again"], proc_table=in_claude(homes, A), pid=300)
    assert code == 0 and [f["label"] for f in favs(homes)] == ["again"]


def test_label_for_saved_session_clash(homes):
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="T")
    make_claude_session(homes.claude, "8f1c2a3b-1111-4000-8000-000000000002", homes.root / "q", ai_title="Other")
    run(["add", A])
    run(["add", "8f1c2a3b-1111-4000-8000-000000000002"])
    code, ctx = run(["add", A, "-l", "other"])
    assert code == 1 and "already used" in ctx.stderr.getvalue()


# 5 ---------------------------------------------------------------------------


def test_tag_takes_one_value(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    code, ctx = run(["add", "-t", "work", "jobs"], proc_table=in_claude(homes, A), pid=300)
    assert code == 0, ctx.stderr.getvalue()
    [f] = favs(homes)
    assert f["label"] == "jobs" and f["tags"] == ["work"]


def test_tag_commas_and_repeats(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    run(["add", A, "-t", "work,client", "-t", "x"])
    assert favs(homes)[0]["tags"] == ["work", "client", "x"]


# 6 ---------------------------------------------------------------------------


def test_release_keeps_someone_elses_lock(tmp_path):
    p = tmp_path / "favorites.json"
    lock = tmp_path / "favorites.json.lock"
    with store.locked(p):
        lock.write_text("someone-else")
    assert lock.read_text() == "someone-else"


def _age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t))


def test_stale_lock_not_broken_while_another_process_breaks_it(tmp_path):
    p = tmp_path / "favorites.json"
    (tmp_path / "favorites.json.lock").write_text("dead")
    _age(tmp_path / "favorites.json.lock", 60)
    (tmp_path / "favorites.json.lock.break").write_text("busy")
    with pytest.raises(DogearError):
        with store.locked(p, timeout=0.3):
            pass


def test_stale_break_lock_recovered(tmp_path):
    p = tmp_path / "favorites.json"
    for name in ("favorites.json.lock", "favorites.json.lock.break"):
        (tmp_path / name).write_text("dead")
        _age(tmp_path / name, 60)
    with store.locked(p, timeout=1.0):
        pass
    assert not (tmp_path / "favorites.json.lock.break").exists()


# 7 ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="POSIX permissions, non-root")
def test_read_only_folder_says_so(tmp_path):
    d = tmp_path / "ro"
    d.mkdir()
    d.chmod(0o500)
    try:
        start = time.monotonic()
        with pytest.raises(DogearError, match="cannot write"):
            with store.locked(d / "favorites.json", timeout=3):
                pass
        assert time.monotonic() - start < 1
    finally:
        d.chmod(0o700)


# 8 ---------------------------------------------------------------------------


class Interrupting(io.StringIO):
    def readline(self, *a):
        raise KeyboardInterrupt


class BrokenPipe(io.StringIO):
    def write(self, s):
        raise BrokenPipeError


def _one_fav(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    run(["add", A])


def test_ctrl_c_in_picker_exits_quietly(homes):
    _one_fav(homes)
    ctx = Context.for_test(stdin_isatty=True, which=lambda n: None)
    ctx.stdin = Interrupting()
    assert main([], ctx) == 130
    assert "Traceback" not in ctx.stderr.getvalue()


def test_broken_pipe_exits_quietly(homes):
    _one_fav(homes)
    ctx = Context.for_test()
    ctx.stdout = BrokenPipe()
    assert main(["ls"], ctx) == 1


# 9 ---------------------------------------------------------------------------


def _w(s):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _fav(**kw):
    f = {"label": "a", "agent": "claude", "session_id": "id", "cwd": "/h/u/x", "title": "T", "tags": [], "note": ""}
    f.update(kw)
    return f


def test_folder_shrinks_before_title():
    f = _fav(cwd="/very/long/path/" + "segment/" * 8, title="An informative session title")
    out = format_table([(1, f)], set(), width=80, color=False, home="/h/u")
    assert "An informative session title" in out
    assert all(_w(line) <= 80 for line in out.splitlines())


def test_wide_characters_align():
    rows = [(1, _fav(title="日本語のセッション", label="jp", tags=["tagq"])), (2, _fav(label="b", tags=["tagz"]))]
    lines = format_table(rows, set(), width=100, color=False, home="/h/u").splitlines()
    # the TAGS column starts at the same display column on every line, wide title or not
    starts = [_w(line[: line.index(tag)]) for line, tag in zip(lines, ["TAGS", "tagq", "tagz"])]
    assert len(set(starts)) == 1
    assert all(_w(line) <= 100 for line in lines)


def test_wide_title_is_cut_by_display_width():
    f = _fav(title="日本語" * 30, note="n")
    out = format_table([(1, f)], set(), width=60, color=False, home="/h/u")
    assert all(_w(line) <= 60 for line in out.splitlines())


# 10 --------------------------------------------------------------------------


def test_non_uuid_transcripts_ignored(homes):
    make_claude_session(homes.claude, A, homes.root / "p")
    other = next((homes.claude / "projects").iterdir()) / "agent-1a2b3c4d.jsonl"
    other.write_text('{"type":"user","cwd":"/x"}\n', encoding="utf-8")
    assert [s.session_id for s in ClaudeAdapter().recent(10)] == [A]


# 11 --------------------------------------------------------------------------


def test_titles_without_parsing_every_line(homes, monkeypatch):
    lines = tuple(json.dumps({"type": "assistant", "message": {"content": "x" * 100}}) for _ in range(1000))
    make_claude_session(homes.claude, A, homes.root / "p", ai_title="Fast", extra_lines=lines)
    import dogear.agents.claude as claude_mod

    calls = []
    real = claude_mod.json.loads
    monkeypatch.setattr(claude_mod.json, "loads", lambda s, *a, **k: calls.append(1) or real(s, *a, **k))
    s = ClaudeAdapter().get(A)
    assert s.title == "Fast" and s.cwd == str(homes.root / "p")
    assert len(calls) < 20


# 12 --------------------------------------------------------------------------


def test_no_fzf_preview_on_windows(monkeypatch):
    seen = {}
    monkeypatch.setattr(picker_mod, "WINDOWS", True)
    ctx = Context.for_test(stdin_isatty=True, which=lambda n: "/fake/fzf", run_fzf=lambda a, t: (seen.setdefault("args", a), (0, "0\talpha\n"))[1])
    assert picker_mod.pick(["alpha"], ctx=ctx, use_fzf="auto", prompt="p", previews=["x"]) == 0
    assert not any(a.startswith("--preview") for a in seen["args"])
