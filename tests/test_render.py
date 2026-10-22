from dogear.render import format_table

HOME = "/h/user"


def fav(label, **kw):
    base = {"label": label, "agent": "claude", "session_id": label + "-id", "cwd": f"{HOME}/code/{label}", "title": "Example session", "tags": [], "note": ""}
    base.update(kw)
    return base


def test_header_and_home_shortening():
    out = format_table([(1, fav("a"))], set(), width=200, color=False, home=HOME)
    lines = out.splitlines()
    assert lines[0].split() == ["#", "LABEL", "AGENT", "FOLDER", "TITLE", "TAGS", "NOTE"]
    assert "~/code/a" in lines[1] and HOME not in lines[1]


def test_missing_marker():
    out = format_table([(1, fav("a")), (2, fav("b"))], {("claude", "b-id")}, width=200, color=False, home=HOME)
    assert "b (missing)" in out and "a (missing)" not in out


def test_fits_width():
    rows = [(i, fav(f"f{i}", title="A fairly long example session title " * 2, note="some note text " * 3, tags=["w"])) for i in range(1, 4)]
    out = format_table(rows, set(), width=80, color=False, home=HOME)
    assert all(len(line) <= 80 for line in out.splitlines())
    assert "…" in out


def test_no_ansi_without_color():
    out = format_table([(1, fav("a"))], {("claude", "a-id")}, width=100, color=False, home=HOME)
    assert "\x1b" not in out


def test_ansi_with_color():
    out = format_table([(1, fav("a"))], set(), width=100, color=True, home=HOME)
    assert "\x1b[1m" in out


def test_tags_joined():
    out = format_table([(3, fav("a", tags=["work", "x"]))], set(), width=200, color=False, home=HOME)
    assert "work,x" in out and out.splitlines()[1].lstrip().startswith("3")
