"""Pure helpers over favourite records (plain dicts, so unknown fields survive)."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from dogear.errors import DogearError


def slugify(text: str, max_len: int = 40) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if len(slug) > max_len:
        cut = slug[:max_len]
        slug = cut.rsplit("-", 1)[0] if "-" in cut else cut
    return slug.strip("-")


def validate_label(label: str) -> None:
    if not label or label.strip() != label or any(c.isspace() for c in label):
        raise DogearError(f"invalid label {label!r}: use a non-empty name without spaces")
    if label.startswith("-"):
        raise DogearError(f"invalid label {label!r}: labels can't start with '-'")
    if label.isdigit():
        raise DogearError(f"invalid label {label!r}: labels can't be all digits (numbers refer to dogear ls)")


def default_label(session) -> str:
    slug = "" if session.title == "(untitled)" else slugify(session.title)
    if not slug:
        return f"{session.agent}-{session.session_id[:8]}"
    if slug.isdigit():
        return f"{session.agent}-{slug}"
    return slug


def unique_label(base: str, existing: set[str]) -> str:
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def ordered(favs: list[dict]) -> list[dict]:
    """Display order: most recently added first; ties put the last appended first."""
    return sorted(reversed(favs), key=lambda f: str(f.get("added_at", "")), reverse=True)


def resolve(favs: list[dict], ref: str) -> dict:
    if ref.isdigit():
        order = ordered(favs)
        n = int(ref)
        if 1 <= n <= len(order):
            return order[n - 1]
    else:
        for f in favs:
            if f.get("label") == ref:
                return f
    raise DogearError(f"no favourite '{ref}'; see dogear ls")


def find_by_session(favs: list[dict], agent: str, session_id: str) -> dict | None:
    for f in favs:
        if f.get("agent") == agent and f.get("session_id") == session_id:
            return f
    return None


def new_favorite(session, *, label: str, note: str, tags: list[str], args: str, now: datetime) -> dict:
    return {
        "agent": session.agent,
        "session_id": session.session_id,
        "cwd": session.cwd,
        "label": label,
        "title": session.title,
        "note": note,
        "tags": list(tags),
        "args": args,
        "added_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
