"""The two actions a chat window has no buttons for, and what they say back.

A browser has a "new conversation" button and a stop button. A messenger has a
text box, so the same two actions have to be *triggered* somehow — and **how** is
the part that differs per platform, so it is not here:

- Telegram delivers `/new` as an ordinary message, with `@botname` appended in
  groups
- Slack routes slash commands to a separate Request URL entirely; they never
  arrive as message events
- Discord's are a structured interactions API, distinct from message content
- WhatsApp has no such convention at all — a user typing `/new` has sent the
  literal text `/new`, and a keyword or a quick-reply button is the local idiom

So recognising a command belongs to the platform (`telegram/commands.py`), and
this file holds only what every platform means by it. Splitting the other way —
one shared parser assuming a leading slash — is what this file used to do, and it
quietly made `/new` un-triggerable on three of the four platforms above.

Whatever the trigger, both actions **bypass the queue**. A stop that waited its
turn behind the work it is trying to stop would be useless, and `hermes-agent`
routes its equivalents around the busy policy for the same reason.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from harness.channels.gateway import ChannelGateway
from harness.skills import Skill


class Command(StrEnum):
    """What a platform decided the user asked for."""

    NEW = "new"
    STOP = "stop"
    # The phone has no `/skills` page. This is its list.
    SKILLS = "skills"


STARTED = "New conversation started."
STOPPED = "Stopped."
NOTHING_TO_STOP = "Nothing is running."
COMMANDS = "Commands: /new, /stop."


def unknown_skill(name: str, skills: Sequence[Skill]) -> str:
    """The reply to a `/word` that is neither a command nor a skill.

    Answered rather than passed to the model: someone typing `/summarise` meant
    a command, and treating it as a prompt produces a confident answer to a
    question they did not ask. The reply lists what they could have typed — the
    gateway raises `UnknownSkill`, each platform sends this.
    """
    listed = ", ".join(f"/{skill.name}" for skill in skills) or "none"
    return f"No skill named {name!r}. Skills: {listed}. {COMMANDS}"


def skills_reply(skills: Sequence[Skill]) -> str:
    """`/skills`: every skill a person may type, with what it is for."""
    if not skills:
        return f"No skills installed. {COMMANDS}"
    lines = "\n".join(f"/{skill.name} — {skill.description}" for skill in skills)
    return f"Skills you can type:\n{lines}\n\n{COMMANDS}"


async def apply(gateway: ChannelGateway, channel: str, chat_id: str, command: Command) -> str:
    """Run one command. @returns what to say back.

    Takes the channel as well as the chat, because one gateway serves every
    platform and a chat id alone does not identify a conversation.
    """
    if command is Command.NEW:
        await gateway.reset(channel, chat_id)
        return STARTED
    if command is Command.STOP:
        return STOPPED if await gateway.stop(channel, chat_id) else NOTHING_TO_STOP
    return skills_reply(gateway.skills.invocable())
