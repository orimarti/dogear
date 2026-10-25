"""Plain-text table for `dogear ls`."""

from __future__ import annotations

import os
import unicodedata

HEADERS = ["#", "LABEL", "AGENT", "FOLDER", "TITLE", "TAGS", "NOTE"]
SHRINK_ORDER = ["NOTE", "FOLDER", "TITLE"]
MIN_WIDTH = 8
GAP = "  "
BOLD, DIM, RESET = "\x1b[1m", "\x1b[2m", "\x1b[0m"


def short_home(path: str, home: str) -> str:
    if path == home:
        return "~"
    for sep in {os.sep, "/"}:
        if path.startswith(home + sep):
            return "~" + path[len(home) :]
    return path


def _char_width(c: str) -> int:
    if unicodedata.combining(c):
        return 0
    return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1


def display_width(text: str) -> int:
    return sum(_char_width(c) for c in text)


def _cut(text: str, width: int) -> str:
    """Fit text into `width` terminal columns, marking a cut with …"""
    if display_width(text) <= width:
        return text
    out, used = "", 0
    for c in text:
        w = _char_width(c)
        if used + w > width - 1:
            break
        out, used = out + c, used + w
    return out + "…"


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - display_width(text), 0)


def format_table(rows: list[tuple[int, dict]], missing: set[tuple[str, str]], *, width: int, color: bool, home: str) -> str:
    cells = []
    gone = []
    for n, f in rows:
        is_missing = (f.get("agent"), f.get("session_id")) in missing
        gone.append(is_missing)
        label = str(f.get("label", "")) + (" (missing)" if is_missing else "")
        note = " ".join(str(f.get("note", "")).split())
        cells.append(
            [
                str(n),
                label,
                str(f.get("agent", "")),
                short_home(str(f.get("cwd", "")), home),
                " ".join(str(f.get("title", "")).split()),
                ",".join(f.get("tags") or []),
                note,
            ]
        )
    widths = [max([display_width(h)] + [display_width(r[i]) for r in cells]) for i, h in enumerate(HEADERS)]
    excess = sum(widths) + len(GAP) * (len(widths) - 1) - width
    for name in SHRINK_ORDER:
        if excess <= 0:
            break
        i = HEADERS.index(name)
        give = min(excess, max(widths[i] - MIN_WIDTH, 0))
        widths[i] -= give
        excess -= give

    def line(values: list[str]) -> str:
        parts = [_pad(_cut(v, w), w) for v, w in zip(values, widths)]
        parts[0] = values[0].rjust(widths[0])
        return GAP.join(parts).rstrip()

    out = [line(HEADERS)]
    if color:
        out[0] = BOLD + out[0] + RESET
    for r, is_missing in zip(cells, gone):
        text = line(r)
        out.append(DIM + text + RESET if color and is_missing else text)
    return "\n".join(out)
