import pytest

from dogear.cli import Context
from dogear.errors import DogearError
from dogear.picker import pick

ROWS = ["alpha", "beta", "gamma"]


def tty_ctx(stdin="", **kw):
    kw.setdefault("which", lambda n: None)
    return Context.for_test(stdin=stdin, stdin_isatty=True, **kw)


def test_numbered_choice():
    ctx = tty_ctx("2\n")
    assert pick(ROWS, ctx=ctx, use_fzf="auto", prompt="pick") == 1
    assert "1  alpha" in ctx.stderr.getvalue()


def test_numbered_eof_cancels():
    assert pick(ROWS, ctx=tty_ctx(""), use_fzf="auto", prompt="pick") is None


def test_numbered_blank_cancels():
    assert pick(ROWS, ctx=tty_ctx("\n"), use_fzf="never", prompt="pick") is None


def test_numbered_out_of_range_reasks():
    assert pick(ROWS, ctx=tty_ctx("9\nx\n3\n"), use_fzf="never", prompt="pick") == 2


def test_no_tty_raises():
    ctx = Context.for_test(stdin="1\n", stdin_isatty=False)
    with pytest.raises(DogearError, match="TTY"):
        pick(ROWS, ctx=ctx, use_fzf="auto", prompt="pick")


def test_empty_rows():
    assert pick([], ctx=tty_ctx("1\n"), use_fzf="never", prompt="pick") is None


def test_fzf_selection():
    seen = {}

    def fake(args, text):
        seen["args"], seen["text"] = args, text
        return 0, "1\tbeta\tmore\n"

    ctx = tty_ctx(which=lambda n: "/fake/fzf", run_fzf=fake)
    assert pick(ROWS, ctx=ctx, use_fzf="auto", prompt="pick", previews=["p0", "p1", "p2"]) == 1
    assert seen["args"][0] == "/fake/fzf"
    assert "0\talpha\tp0" in seen["text"]
    assert any(a.startswith("--preview") for a in seen["args"])


def test_fzf_cancel():
    ctx = tty_ctx(which=lambda n: "/fake/fzf", run_fzf=lambda a, t: (130, ""))
    assert pick(ROWS, ctx=ctx, use_fzf="auto", prompt="pick") is None


def test_never_ignores_fzf():
    def boom(a, t):
        raise AssertionError("fzf must not run")

    ctx = tty_ctx("1\n", which=lambda n: "/fake/fzf", run_fzf=boom)
    assert pick(ROWS, ctx=ctx, use_fzf="never", prompt="pick") == 0


def test_always_without_fzf_errors():
    with pytest.raises(DogearError, match="fzf"):
        pick(ROWS, ctx=tty_ctx("1\n"), use_fzf="always", prompt="pick")
