"""Fitting one reply into a platform's per-message limit."""

from __future__ import annotations


def split_message(text: str, limit: int) -> list[str]:
    """One reply as one or more messages, each within `limit` characters."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit]
        cut = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        parts.append(rest)
    return parts
