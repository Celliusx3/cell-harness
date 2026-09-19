"""The slash commands a chat accepts, and what they say back."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from harness.channels.gateway import ChannelGateway
from harness.skills import Skill


class Command(StrEnum):
    """What a platform decided the user asked for."""

    NEW = "new"
    STOP = "stop"
    SKILLS = "skills"
    COMPACT = "compact"


STARTED = "New conversation started."
STOPPED = "Stopped."
NOTHING_TO_STOP = "Nothing is running."
COMPACTING = "Compacting the conversation to free up context…"
NOTHING_TO_COMPACT = "Nothing to compact yet."
COMMANDS = "Commands: /new, /stop, /compact."


def unknown_skill(name: str, skills: Sequence[Skill]) -> str:
    """The reply to a `/word` that is neither a command nor a skill."""
    listed = ", ".join(f"/{skill.name}" for skill in skills) or "none"
    return f"No skill named {name!r}. Skills: {listed}. {COMMANDS}"


def skills_reply(skills: Sequence[Skill]) -> str:
    """`/skills`: every skill a person may type, with what it is for."""
    if not skills:
        return f"No skills installed. {COMMANDS}"
    lines = "\n".join(f"/{skill.name} — {skill.description}" for skill in skills)
    return f"Skills you can type:\n{lines}\n\n{COMMANDS}"


async def apply(gateway: ChannelGateway, channel: str, chat_id: str, command: Command) -> str:
    """Run one command."""
    if command is Command.NEW:
        await gateway.reset(channel, chat_id)
        return STARTED
    if command is Command.STOP:
        return STOPPED if await gateway.stop(channel, chat_id) else NOTHING_TO_STOP
    if command is Command.COMPACT:
        started = await gateway.compact_chat(channel, chat_id)
        return COMPACTING if started is not None else NOTHING_TO_COMPACT
    return skills_reply(gateway.skills.invocable())
