"""The favourites file: atomic writes, a backup, and a lock around read-modify-write."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
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


@contextmanager
def locked(path: Path, timeout: float = 5.0, stale: float = 10.0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale:
                    lock.unlink()
                    continue
            except FileNotFoundError:
                continue
            except PermissionError:
                pass  # Windows: the holder is replacing it right now
            if time.monotonic() >= deadline:
                raise DogearError(f"{lock} is held by another dogear; try again") from None
            time.sleep(0.05)
        except PermissionError:
            # Windows reports a lock file being deleted as access denied
            if time.monotonic() >= deadline:
                raise DogearError(f"{lock} is held by another dogear; try again") from None
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def transaction(path: Path) -> Iterator[dict]:
    """Load, let the caller change the data, save — all under the lock."""
    with locked(path):
        data = load(path)
        yield data
        save(path, data)
