"""Agent adapters. Adding an agent means adding one module with an Adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from dogear.proctree import ProcessTable


@dataclass(frozen=True)
class Session:
    agent: str
    session_id: str
    cwd: str
    title: str
    mtime: float
    path: Path | None


class Adapter(Protocol):
    name: str

    def find(self, prefix: str) -> list[Session]: ...
    def get(self, session_id: str) -> Session | None: ...
    def exists(self, session_id: str) -> bool: ...
    def recent(self, limit: int) -> list[Session]: ...
    def is_agent_process(self, command: str) -> bool: ...
    def detect(self, pid: int, table: "ProcessTable") -> list[Session]: ...
    def resume_args(self, session_id: str) -> list[str]: ...


def command_basename(command: str) -> str:
    """'C:\\x\\claude.exe' -> 'claude'; '-zsh' -> 'zsh' (login shells)."""
    base = command.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if base.lower().endswith(".exe"):
        base = base[:-4]
    return base.lstrip("-")


def newest_by_id(paths_with_ids: list[tuple[str, Path]]) -> dict[str, Path]:
    """Several files can exist for one session id; keep the newest (spec §11b)."""
    best: dict[str, tuple[float, Path]] = {}
    for sid, p in paths_with_ids:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if sid not in best or m > best[sid][0]:
            best[sid] = (m, p)
    return {sid: p for sid, (m, p) in best.items()}


def newest_first(by_id: dict[str, Path], limit: int) -> list[tuple[str, Path]]:
    """Sort by mtime without failing when a file disappears meanwhile (agents prune old ones)."""
    stamped = []
    for sid, p in by_id.items():
        try:
            stamped.append((p.stat().st_mtime, sid, p))
        except OSError:
            continue
    stamped.sort(key=lambda t: t[0], reverse=True)
    return [(sid, p) for _, sid, p in stamped[:limit]]


def get_adapters() -> dict[str, Adapter]:
    from dogear.agents.claude import ClaudeAdapter
    from dogear.agents.codex import CodexAdapter

    return {"claude": ClaudeAdapter(), "codex": CodexAdapter()}


def find_sessions(prefix: str, agent: str | None = None) -> list[Session]:
    out: list[Session] = []
    for name, adapter in get_adapters().items():
        if agent is None or agent == name:
            out.extend(adapter.find(prefix))
    return out
