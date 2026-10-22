import os
import sys

import pytest

from dogear import proctree
from tests.fakes import FakeProcessTable


def test_ancestors_walks_up_and_stops():
    t = FakeProcessTable({100: {"ppid": 50, "cmd": "dogear"}, 50: {"ppid": 10, "cmd": "sh"}, 10: {"ppid": 1, "cmd": "claude"}})
    assert list(proctree.ancestors(t, 100)) == [(50, "sh"), (10, "claude")]


def test_ancestors_cycle_terminates():
    t = FakeProcessTable({5: {"ppid": 6, "cmd": "a"}, 6: {"ppid": 5, "cmd": "b"}})
    assert len(list(proctree.ancestors(t, 5))) <= 2


def test_ancestors_unknown_pid():
    assert list(proctree.ancestors(FakeProcessTable({}), 42)) == []


def test_default_table_class():
    t = proctree.default_table()
    expected = {"win32": proctree.WindowsTable, "linux": proctree.ProcfsTable}.get(sys.platform, proctree.PosixPsTable)
    assert isinstance(t, expected)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process table")
def test_real_parent_is_ppid():
    ppid, cmd = proctree.default_table().parent(os.getpid())
    assert ppid == os.getppid() and cmd


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process table")
def test_real_start_time_is_plausible():
    import time

    start = proctree.default_table().start_time(os.getpid())
    assert start is not None and time.time() - 3600 < start <= time.time() + 2


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process table")
def test_real_open_files_and_cwd(tmp_path):
    t = proctree.default_table()
    f = tmp_path / "rollout-test.jsonl"
    with f.open("w"):
        files = [os.path.realpath(p) for p in t.open_files(os.getpid())]
        assert os.path.realpath(f) in files
    assert os.path.realpath(t.cwd(os.getpid())) == os.path.realpath(os.getcwd())


def test_missing_pid_is_none():
    t = proctree.default_table()
    assert t.parent(2**22 + 12345) is None
