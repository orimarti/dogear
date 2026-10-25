"""Build a throwaway HOME with synthetic Claude Code and Codex sessions for the demo GIF.

Usage: python docs/demo/setup.py DIR   (DIR is wiped and recreated)
Nothing here touches your real ~/.claude, ~/.codex or dogear favourites.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

CLAUDE = [
    ("3f9a1c2e-5b7d-4e8f-9a0b-1c2d3e4f5a6b", "code/todo-app", "Add dark mode toggle"),
    ("7c4e2a9b-1d3f-4a5b-8c6d-9e0f1a2b3c4d", "code/infra", "Terraform drift check"),
]
CODEX = [
    ("019a2b3c-4d5e-7f60-8a9b-0c1d2e3f4a5b", "code/site", "Docs site refresh"),
]


def write_jsonl(path: Path, lines: list[dict], mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def main(root: Path) -> None:
    shutil.rmtree(root, ignore_errors=True)
    now = time.time()
    meta = {}
    for i, (sid, rel, title) in enumerate(CLAUDE):
        cwd = root / rel
        cwd.mkdir(parents=True)
        slug = str(cwd).replace("/", "-").replace(".", "-")
        write_jsonl(
            root / ".claude" / "projects" / slug / f"{sid}.jsonl",
            [
                {"type": "user", "cwd": str(cwd), "sessionId": sid, "message": {"role": "user", "content": title}},
                {"type": "ai-title", "aiTitle": title, "sessionId": sid},
            ],
            now - 3600 * (i + 1),
        )
        meta[sid] = {"cwd": str(cwd), "title": title}
    for sid, rel, title in CODEX:
        cwd = root / rel
        cwd.mkdir(parents=True)
        when = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now - 7200))
        day = when[:10].replace("-", "/")
        write_jsonl(
            root / ".codex" / "sessions" / day / f"rollout-{when.replace(':', '-')}-{sid}.jsonl",
            [{"timestamp": when, "type": "session_meta", "payload": {"id": sid, "cwd": str(cwd), "timestamp": when}}],
            now - 7200,
        )
        (root / ".codex" / "session_index.jsonl").write_text(
            json.dumps({"id": sid, "thread_name": title, "updated_at": when + "Z"}) + "\n", encoding="utf-8"
        )
        meta[sid] = {"cwd": str(cwd), "title": title}

    (root / ".demo").mkdir()
    (root / ".demo" / "sessions.json").write_text(json.dumps(meta), encoding="utf-8")
    bin_dir = root / ".demo" / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex"):
        shutil.copy(HERE / "fake-agent.js", bin_dir / name)
        (bin_dir / name).chmod(0o755)

    # Two favourites saved earlier, so the list isn't empty when the demo starts.
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "DOGEAR_HOME", "XDG_CONFIG_HOME")}
    env["HOME"] = str(root)
    for argv in (
        ["dogear", "add", CODEX[0][0], "-l", "docs-site", "-t", "web"],
        ["dogear", "add", CLAUDE[1][0], "-l", "infra-drift", "-t", "ops", "-n", "check prod"],
    ):
        subprocess.run(argv, env=env, check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
