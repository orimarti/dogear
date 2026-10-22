import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import pytest

from dogear import store
from dogear.errors import DogearError


def test_load_missing_returns_empty(tmp_path):
    assert store.load(tmp_path / "favorites.json") == {"version": 1, "favorites": []}


def test_save_roundtrip_preserves_unknown_fields(tmp_path):
    p = tmp_path / "d" / "favorites.json"
    data = {"version": 1, "extra": 1, "favorites": [{"label": "a", "future": "x"}]}
    store.save(p, data)
    again = store.load(p)
    store.save(p, again)
    assert store.load(p) == data


def test_save_keeps_bak(tmp_path):
    p = tmp_path / "favorites.json"
    store.save(p, {"version": 1, "favorites": [{"label": "first"}]})
    store.save(p, {"version": 1, "favorites": [{"label": "second"}]})
    bak = json.loads((tmp_path / "favorites.json.bak").read_text())
    assert bak["favorites"][0]["label"] == "first"
    assert store.load(p)["favorites"][0]["label"] == "second"


def test_save_atomic_no_temp_left(tmp_path):
    p = tmp_path / "d" / "favorites.json"
    store.save(p, {"version": 1, "favorites": []})
    store.save(p, {"version": 1, "favorites": []})
    assert sorted(f.name for f in p.parent.iterdir()) == ["favorites.json", "favorites.json.bak"]


def test_corrupt_file_raises_and_is_untouched(tmp_path):
    p = tmp_path / "favorites.json"
    p.write_text("{not json")
    with pytest.raises(DogearError) as e:
        with store.transaction(p) as data:
            data["favorites"].append({"label": "x"})
    assert "favorites.json" in str(e.value) and ".bak" in str(e.value)
    assert p.read_text() == "{not json"


def test_wrong_shape_rejected(tmp_path):
    p = tmp_path / "favorites.json"
    p.write_text('{"version": 1, "favorites": {}}')
    with pytest.raises(DogearError):
        store.load(p)


def test_newer_version_rejected(tmp_path):
    p = tmp_path / "favorites.json"
    p.write_text('{"version": 2, "favorites": []}')
    with pytest.raises(DogearError, match="version"):
        store.load(p)


def test_stale_lock_is_broken(tmp_path):
    p = tmp_path / "favorites.json"
    lock = tmp_path / "favorites.json.lock"
    lock.write_text("123")
    old = time.time() - 60
    os.utime(lock, (old, old))
    with store.locked(p, timeout=0.5):
        assert lock.exists()
    assert not lock.exists()


def test_lock_timeout(tmp_path):
    p = tmp_path / "favorites.json"
    (tmp_path / "favorites.json.lock").write_text("123")
    with pytest.raises(DogearError, match="lock"):
        with store.locked(p, timeout=0.2):
            pass


def _append(args):
    path, i = args
    with store.transaction(path) as data:
        data["favorites"].append({"label": f"f{i}"})


def test_concurrent_transactions_lose_nothing(tmp_path):
    p = tmp_path / "favorites.json"
    with ProcessPoolExecutor(4) as ex:
        list(ex.map(_append, [(p, i) for i in range(20)]))
    labels = {f["label"] for f in store.load(p)["favorites"]}
    assert labels == {f"f{i}" for i in range(20)}
