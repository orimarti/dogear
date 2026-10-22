"""Codex CLI session store (read-only). Internal files observed on codex-cli 0.16x."""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from dogear.agents import Session, command_basename, newest_by_id
from dogear.jsonl import iter_jsonl
from dogear.paths import codex_home

UUID_LEN = 36


def _first_line(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            obj = json.loads(f.readline())
    except (OSError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}


class CodexAdapter:
    name = "codex"

    def __init__(self, home: Path | None = None):
        self.home = home or codex_home()

    # store -----------------------------------------------------------------

    def _rollouts(self, prefix: str = "") -> dict[str, Path]:
        pattern = str(self.home / "sessions" / "*" / "*" / "*" / "rollout-*.jsonl")
        found = []
        for p in glob.glob(pattern):
            sid = Path(p).stem[-UUID_LEN:]
            if sid.startswith(prefix):
                found.append((sid, Path(p)))
        return newest_by_id(found)

    def _titles(self) -> dict[str, str]:
        titles: dict[str, str] = {}
        for obj in iter_jsonl(self.home / "session_index.jsonl"):
            sid, name = obj.get("id"), obj.get("thread_name")
            if isinstance(sid, str) and isinstance(name, str) and name.strip():
                titles[sid] = name.strip()
        return titles

    def _session(self, sid: str, path: Path, titles: dict[str, str]) -> Session:
        meta = _first_line(path)
        payload = meta.get("payload") if meta.get("type") == "session_meta" else None
        payload = payload if isinstance(payload, dict) else {}
        if isinstance(payload.get("id"), str):
            sid = payload["id"]
        cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        return Session("codex", sid, cwd, titles.get(sid, "(untitled)"), mtime, path)

    def find(self, prefix: str) -> list[Session]:
        titles = self._titles()
        return [self._session(sid, p, titles) for sid, p in sorted(self._rollouts(prefix).items())]

    def get(self, session_id: str) -> Session | None:
        p = self._rollouts(session_id).get(session_id)
        return self._session(session_id, p, self._titles()) if p else None

    def exists(self, session_id: str) -> bool:
        return session_id in self._rollouts(session_id)

    def recent(self, limit: int) -> list[Session]:
        items = self._rollouts()
        newest = sorted(items.items(), key=lambda kv: kv[1].stat().st_mtime, reverse=True)[:limit]
        titles = self._titles()
        return [self._session(sid, p, titles) for sid, p in newest]

    # processes -------------------------------------------------------------

    def is_agent_process(self, command: str) -> bool:
        return command_basename(command) == "codex"

    def detect(self, pid: int, table) -> list[Session]:
        """The rollout the process has open; else rollouts in its cwd written since it started."""
        sessions_dir = os.path.realpath(self.home / "sessions")
        open_ids = []
        for f in table.open_files(pid):
            real = os.path.realpath(f)
            name = os.path.basename(real)
            if real.startswith(sessions_dir + os.sep) and name.startswith("rollout-") and name.endswith(".jsonl"):
                open_ids.append(name[: -len(".jsonl")][-UUID_LEN:])
        if open_ids:
            return [s for sid in dict.fromkeys(open_ids) if (s := self.get(sid))]
        cwd, start = table.cwd(pid), table.start_time(pid)
        if not cwd or start is None:
            return []
        real_cwd = os.path.realpath(cwd)
        titles = self._titles()
        out = []
        for sid, p in sorted(self._rollouts().items()):
            try:
                if p.stat().st_mtime < start:
                    continue
            except OSError:
                continue
            s = self._session(sid, p, titles)
            if s.cwd and os.path.realpath(s.cwd) == real_cwd:
                out.append(s)
        return out

    def resume_args(self, session_id: str) -> list[str]:
        return ["resume", session_id]
