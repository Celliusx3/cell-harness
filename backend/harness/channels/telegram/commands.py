"""Recognising a command in a Telegram message."""

from __future__ import annotations

from harness.channels.commands import Command

_NAMES = {
    "/new": Command.NEW,
    "/stop": Command.STOP,
    "/skills": Command.SKILLS,
    "/compact": Command.COMPACT,
}


def parse(text: str) -> Command | None:
    """The command this message asks for, or `None` for anything else."""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    # Telegram appends the bot's name in groups: `/new@my_bot`.
    word = stripped.split()[0].split("@")[0].lower()
    return _NAMES.get(word)
