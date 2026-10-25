"""Synthetic agent stores and process tables for tests. Nothing here is real data."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _write_lines(path: Path, lines: list, mtime: float | None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line if isinstance(line, str) else json.dumps(line))
            f.write("\n")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def make_claude_session(
    claude_home: Path,
    session_id: str,
    cwd: str,
    *,
    ai_title: str | list[str] | None = None,
    custom_title: str | None = None,
    first_prompt: str | list | None = "Example prompt",
    mtime: float | None = None,
    extra_lines: tuple = (),
) -> Path:
    slug = str(cwd).replace("/", "-").replace("\\", "-").replace(".", "-").replace(":", "-")
    lines: list = [{"type": "permission-mode", "sessionId": session_id}]
    if first_prompt is not None:
        lines.append(
            {
                "type": "user",
                "cwd": str(cwd),
                "sessionId": session_id,
                "message": {"role": "user", "content": first_prompt},
            }
        )
    else:
        lines.append({"type": "attachment", "cwd": str(cwd), "sessionId": session_id})
    lines.append({"type": "assistant", "cwd": str(cwd), "sessionId": session_id, "message": {"content": []}})
    titles = [ai_title] if isinstance(ai_title, str) else (ai_title or [])
    for t in titles:
        lines.append({"type": "ai-title", "aiTitle": t, "sessionId": session_id})
    if custom_title is not None:
        lines.append({"type": "custom-title", "customTitle": custom_title, "sessionId": session_id})
    lines.extend(extra_lines)
    return _write_lines(claude_home / "projects" / slug / f"{session_id}.jsonl", lines, mtime)


def write_claude_live(claude_home: Path, pid: int, session_id: str, cwd: str, name: str = "") -> Path:
    p = claude_home / "sessions" / f"{pid}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"pid": pid, "sessionId": session_id, "cwd": str(cwd), "name": name, "status": "busy"})
    )
    return p


def make_codex_rollout(
    codex_home: Path,
    session_id: str,
    cwd: str,
    *,
    when: str = "2026-01-02T03:04:05",
    mtime: float | None = None,
) -> Path:
    day = when[:10].replace("-", "/")
    stamp = when.replace(":", "-")
    path = codex_home / "sessions" / day / f"rollout-{stamp}-{session_id}.jsonl"
    lines = [
        {"timestamp": when, "type": "session_meta", "payload": {"id": session_id, "cwd": str(cwd), "timestamp": when}},
        {"timestamp": when, "type": "event_msg", "payload": {"type": "user_message", "message": "Example prompt"}},
    ]
    return _write_lines(path, lines, mtime)


def append_codex_index(codex_home: Path, session_id: str, thread_name: str) -> None:
    codex_home.mkdir(parents=True, exist_ok=True)
    with (codex_home / "session_index.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"id": session_id, "thread_name": thread_name, "updated_at": "2026-01-02T03:04:05Z"}))
        f.write("\n")


class FakeProcessTable:
    """procs: {pid: {"ppid": int, "cmd": str, "files": [...], "cwd": str, "start": float}}"""

    def __init__(self, procs: dict[int, dict]):
        self.procs = procs

    def parent(self, pid: int):
        p = self.procs.get(pid)
        return (p["ppid"], p["cmd"]) if p else None

    def open_files(self, pid: int) -> list[str]:
        return list(self.procs.get(pid, {}).get("files", []))

    def cwd(self, pid: int):
        return self.procs.get(pid, {}).get("cwd")

    def start_time(self, pid: int):
        return self.procs.get(pid, {}).get("start")
