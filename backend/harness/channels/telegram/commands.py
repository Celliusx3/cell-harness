"""Recognising a command in a Telegram message."""

from __future__ import annotations

from harness.channels.commands import ChatCommand, Command, command_words, mode_command

_NAMES = {
    "/new": Command.NEW,
    "/stop": Command.STOP,
    "/skills": Command.SKILLS,
    "/compact": Command.COMPACT,
}


def parse(text: str) -> ChatCommand | None:
    """The command this message asks for, or `None` for anything else."""
    mode = mode_command(text)
    if mode is not None:
        return mode
    words = command_words(text)
    return _NAMES.get(words[0]) if words else None
