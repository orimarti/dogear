"""Claude Code session store (read-only). Internal files observed on Claude Code 2.1.x."""

from __future__ import annotations

import glob
import json
from pathlib import Path

from dogear.agents import Session, command_basename, newest_by_id, newest_first
from dogear.jsonl import iter_jsonl
from dogear.paths import claude_home

TITLE_LEN = 60


def _prompt_text(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = next(
            (b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"),
            "",
        )
    else:
        return ""
    text = " ".join(str(text).split())
    if text.startswith("<"):  # command wrappers and other meta content, not a real prompt
        return ""
    return text


def _shorten(text: str) -> str:
    return text if len(text) <= TITLE_LEN else text[: TITLE_LEN - 1].rstrip() + "…"


class ClaudeAdapter:
    name = "claude"

    def __init__(self, home: Path | None = None):
        self.home = home or claude_home()

    # store -----------------------------------------------------------------

    def _transcripts(self, prefix: str = "") -> dict[str, Path]:
        pattern = str(self.home / "projects" / "*" / f"{glob.escape(prefix)}*.jsonl")
        return newest_by_id([(Path(p).stem, Path(p)) for p in glob.glob(pattern)])

    def _session(self, sid: str, path: Path) -> Session:
        custom = ai = prompt = ""
        cwd = ""
        for obj in iter_jsonl(path):
            t = obj.get("type")
            if not cwd and isinstance(obj.get("cwd"), str):
                cwd = obj["cwd"]
            if t == "custom-title" and isinstance(obj.get("customTitle"), str):
                custom = obj["customTitle"]
            elif t == "ai-title" and isinstance(obj.get("aiTitle"), str):
                ai = obj["aiTitle"]
            elif t == "user" and not prompt and not obj.get("isMeta"):
                prompt = _prompt_text(obj.get("message"))
        title = custom.strip() or ai.strip() or (_shorten(prompt) if prompt else "(untitled)")
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        return Session("claude", sid, cwd, title, mtime, path)

    def find(self, prefix: str) -> list[Session]:
        return [self._session(sid, p) for sid, p in sorted(self._transcripts(prefix).items())]

    def get(self, session_id: str) -> Session | None:
        p = self._transcripts(session_id).get(session_id)
        return self._session(session_id, p) if p else None

    def exists(self, session_id: str) -> bool:
        return session_id in self._transcripts(session_id)

    def recent(self, limit: int) -> list[Session]:
        return [self._session(sid, p) for sid, p in newest_first(self._transcripts(), limit)]

    # processes -------------------------------------------------------------

    def is_agent_process(self, command: str) -> bool:
        norm = command.replace("\\", "/")
        return (
            command_basename(command) == "claude"
            or "/claude/versions/" in norm
            or "/@anthropic-ai/claude-code/" in norm
        )

    def detect(self, pid: int, table) -> list[Session]:
        """Claude writes sessions/<pid>.json for each live process; stale files are ignored."""
        try:
            live = json.loads((self.home / "sessions" / f"{pid}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []
        if not isinstance(live, dict) or live.get("pid") != pid or not isinstance(live.get("sessionId"), str):
            return []
        sid = live["sessionId"]
        found = self.get(sid)
        if found:
            return [found]
        cwd = live.get("cwd") if isinstance(live.get("cwd"), str) else ""
        name = live.get("name") if isinstance(live.get("name"), str) and live.get("name") else "(untitled)"
        return [Session("claude", sid, cwd, name, 0.0, None)]

    def resume_args(self, session_id: str) -> list[str]:
        return ["--resume", session_id]
