"""Recognising a command in a Telegram message.

Telegram's convention, and only Telegram's: a leading `/`, optionally suffixed
with `@botname` when the bot is in a group. What the command *does* is shared —
see `channels/commands.py`.
"""

from __future__ import annotations

from harness.channels.commands import Command

_NAMES = {
    "/new": Command.NEW,
    "/stop": Command.STOP,
    "/skills": Command.SKILLS,
    "/compact": Command.COMPACT,
}


def parse(text: str) -> Command | None:
    """The command this message asks for, or `None` for anything else.

    Any other slash word goes through to the gateway, because `/find-place` is
    a skill and only the catalog knows that. A word that is neither comes back
    as `UnknownSkill` and is answered there — never handed to the model.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    # `/new@my_bot` — Telegram appends the bot's name in groups. Without this the
    # command silently becomes a prompt the moment the bot joins one.
    word = stripped.split()[0].split("@")[0].lower()
    return _NAMES.get(word)
