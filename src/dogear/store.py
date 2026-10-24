"""The favourites file: atomic writes, a backup, and a lock around read-modify-write."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from dogear.errors import DogearError

VERSION = 1


def _empty() -> dict:
    return {"version": VERSION, "favorites": []}


def load(path: Path) -> dict:
    if not path.exists():
        return _empty()
    hint = f"fix it by hand or restore {path.name}.bak"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise DogearError(f"{path} is not valid JSON ({e}); {hint}") from None
    if not isinstance(data, dict) or not isinstance(data.get("favorites"), list):
        raise DogearError(f"{path} has an unexpected shape; {hint}")
    if not all(isinstance(f, dict) for f in data["favorites"]):
        raise DogearError(f"{path} has an unexpected shape; {hint}")
    version = data.get("version", VERSION)
    if not isinstance(version, int) or version > VERSION:
        raise DogearError(f"{path} has version {version!r}; this dogear understands version {VERSION}")
    return data


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".favorites.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _try_create(path: Path, token: str) -> bool:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except PermissionError:
        if not os.access(path.parent, os.W_OK):
            raise DogearError(f"cannot write to {path.parent}") from None
        return False  # Windows reports a lock file being deleted as access denied
    with os.fdopen(fd, "w") as f:
        f.write(token)
    return True


def _is_stale(path: Path, stale: float) -> bool:
    try:
        return time.time() - path.stat().st_mtime > stale
    except OSError:
        return False


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _break_if_stale(lock: Path, stale: float) -> None:
    """Remove a lock left by a crashed dogear. One breaker at a time, and it re-checks
    staleness while holding the breaker lock, so a fresh lock is never removed."""
    if not _is_stale(lock, stale):
        return
    breaker = lock.with_name(lock.name + ".break")
    if _is_stale(breaker, stale):  # a breaker crashed mid-break
        _unlink(breaker)
    if not _try_create(breaker, "break"):
        return
    try:
        if _is_stale(lock, stale):
            _unlink(lock)
    finally:
        _unlink(breaker)


@contextmanager
def locked(path: Path, timeout: float = 5.0, stale: float = 10.0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    token = f"{os.getpid()}-{uuid.uuid4().hex}"
    deadline = time.monotonic() + timeout
    while not _try_create(lock, token):
        _break_if_stale(lock, stale)
        if time.monotonic() >= deadline:
            raise DogearError(f"{lock} is held by another dogear; try again")
        time.sleep(0.05)
    try:
        yield
    finally:
        try:  # only remove our own lock, never one another process took over
            if lock.read_text() == token:
                lock.unlink()
        except OSError:
            pass


@contextmanager
def transaction(path: Path) -> Iterator[dict]:
    """Load, let the caller change the data, save — all under the lock."""
    with locked(path):
        data = load(path)
        yield data
        save(path, data)
