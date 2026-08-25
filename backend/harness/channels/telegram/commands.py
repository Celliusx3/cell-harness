"""Recognising a command in a Telegram message.

Telegram's convention, and only Telegram's: a leading `/`, optionally suffixed
with `@botname` when the bot is in a group. What the command *does* is shared —
see `channels/commands.py`.
"""

from __future__ import annotations

from harness.channels.commands import Command

_NAMES = {"/new": Command.NEW, "/stop": Command.STOP}


def parse(text: str) -> Command | None:
    """The command this message asks for, or `None` if it is an ordinary prompt.

    `UNKNOWN` rather than `None` for an unrecognised slash word: the user clearly
    meant a command, so it is answered with help instead of handed to the model,
    which would otherwise produce a confident reply to a question nobody asked.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    # `/new@my_bot` — Telegram appends the bot's name in groups. Without this the
    # command silently becomes a prompt the moment the bot joins one.
    word = stripped.split()[0].split("@")[0].lower()
    return _NAMES.get(word, Command.UNKNOWN)
