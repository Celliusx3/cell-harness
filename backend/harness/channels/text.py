"""Fitting one reply into a platform's per-message limit.

Every text platform has one — Telegram 4096, Discord 2000 — and every library
fails the send rather than splitting for you. Our own rules forbid truncating
anything user-facing, so the reply goes out as several messages, cut where the
text already breaks. Platform-neutral, which is why it lives beside the
platforms and not inside one of them.
"""

from __future__ import annotations


def split_message(text: str, limit: int) -> list[str]:
    """One reply as one or more messages, each within `limit` characters.

    Splits at the latest paragraph break that fits, then the latest line break,
    then the latest space — falling back to a hard cut only for text with no
    break in `limit` characters at all (a pasted token, a base64 blob). A hard
    cut mid-word is visibly broken, so it is the last resort rather than the
    implementation.
    """
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    rest = text
    while len(rest) > limit:
        window = rest[:limit]
        cut = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
        # `cut <= 0` covers both "no break found" (-1) and a break at the very
        # start, which would make no progress and loop forever.
        if cut <= 0:
            cut = limit
        parts.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        parts.append(rest)
    return parts
