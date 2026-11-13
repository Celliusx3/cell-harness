"""A saved key as a page may see it: its last four characters, and only when that hides the rest."""

from __future__ import annotations

SHOWN_CHARACTERS = 4
MIN_MASKABLE_LENGTH = 8


def last_four(value: str) -> str | None:
    """The last four characters of a key of eight or more; `None` for a shorter one."""
    return value[-SHOWN_CHARACTERS:] if len(value) >= MIN_MASKABLE_LENGTH else None
