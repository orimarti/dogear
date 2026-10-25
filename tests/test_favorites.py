from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from dogear import favorites as fv
from dogear.errors import DogearError

SID = "8f1c2a3b-0000-4000-8000-000000000001"


def sess(title, agent="claude"):
    return SimpleNamespace(agent=agent, session_id=SID, cwd="/tmp/p", title=title)


def test_slugify():
    assert fv.slugify("New jobs API!") == "new-jobs-api"
    assert fv.slugify("Café — résumé") == "cafe-resume"
    assert fv.slugify("日本語") == ""
    long = fv.slugify("word " * 30)
    assert len(long) <= 40 and not long.endswith("-")


def test_default_label():
    assert fv.default_label(sess("New jobs API")) == "new-jobs-api"
    assert fv.default_label(sess("日本語")) == "claude-8f1c2a3b"
    assert fv.default_label(sess("(untitled)")) == "claude-8f1c2a3b"
    assert fv.default_label(sess("2024", agent="codex")) == "codex-2024"


def test_unique_label():
    assert fv.unique_label("x", {"x", "x-2"}) == "x-3"
    assert fv.unique_label("y", {"x"}) == "y"


@pytest.mark.parametrize("bad", ["", "a b", "12", " "])
def test_validate_label_rejects(bad):
    with pytest.raises(DogearError):
        fv.validate_label(bad)


def test_validate_label_accepts():
    fv.validate_label("jobs-api")
    fv.validate_label("v2")


def favs():
    return [
        {"label": "old", "added_at": "2026-01-01T00:00:00Z"},
        {"label": "new", "added_at": "2026-03-01T00:00:00Z"},
        {"label": "mid", "added_at": "2026-02-01T00:00:00Z"},
        {"label": "mid2", "added_at": "2026-02-01T00:00:00Z"},
    ]


def test_ordered_newest_first_ties_last_appended_first():
    assert [f["label"] for f in fv.ordered(favs())] == ["new", "mid2", "mid", "old"]


def test_resolve():
    f = favs()
    assert fv.resolve(f, "1")["label"] == "new"
    assert fv.resolve(f, "4")["label"] == "old"
    assert fv.resolve(f, "mid")["label"] == "mid"
    for ref in ("5", "0", "nope"):
        with pytest.raises(DogearError, match=f"no favourite '{ref}'"):
            fv.resolve(f, ref)


def test_find_by_session():
    f = [{"agent": "claude", "session_id": SID, "label": "a"}]
    assert fv.find_by_session(f, "claude", SID)["label"] == "a"
    assert fv.find_by_session(f, "codex", SID) is None


def test_new_favorite_keys():
    now = datetime(2026, 10, 23, 10, 0, 0, tzinfo=timezone.utc)
    f = fv.new_favorite(sess("T"), label="t", note="n", tags=["w"], args="--x", now=now)
    assert set(f) == {"agent", "session_id", "cwd", "label", "title", "note", "tags", "args", "added_at"}
    assert f["added_at"] == "2026-10-23T10:00:00Z"
    assert f["title"] == "T" and f["tags"] == ["w"]
