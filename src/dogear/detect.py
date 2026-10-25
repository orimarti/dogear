"""Find the agent session dogear is running inside. Never guesses."""

from __future__ import annotations

import os

from dogear.agents import Adapter, Session
from dogear.errors import DogearError
from dogear.proctree import ProcessTable, ancestors


class DetectionError(DogearError):
    def __init__(self, agent: str, candidates: list[Session]):
        self.agent = agent
        self.candidates = candidates
        if candidates:
            lines = "\n".join(f"  {c.session_id}  {c.title}" for c in candidates)
            msg = f"found {len(candidates)} possible {agent} sessions here:\n{lines}\n"
        else:
            msg = f"could not tell which {agent} session this is; "
        super().__init__(msg + "run dogear add <session-id>")


def detect_current(adapters: dict[str, Adapter], table: ProcessTable, pid: int | None = None) -> Session | None:
    """The current session, None when not inside an agent, DetectionError when unsure."""
    for apid, cmd in ancestors(table, os.getpid() if pid is None else pid):
        for adapter in adapters.values():
            if adapter.is_agent_process(cmd):
                candidates = adapter.detect(apid, table)
                if len(candidates) == 1:
                    return candidates[0]
                raise DetectionError(adapter.name, candidates)
    return None
