"""The slash commands a chat accepts, and what they say back."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import get_args

from harness.channels.service.gateway import ChannelGateway
from harness.skills import Skill
from harness.tools import ApprovalMode


class Command(StrEnum):
    """What a platform decided the user asked for."""

    NEW = "new"
    STOP = "stop"
    SKILLS = "skills"
    COMPACT = "compact"


@dataclass(frozen=True)
class ModeQuestion:
    """`/mode` alone: which mode the chat is in."""


@dataclass(frozen=True)
class ModeChoice:
    """`/mode ask` or `/mode auto`: the mode to switch the chat to."""

    mode: ApprovalMode


@dataclass(frozen=True)
class UnknownModeWord:
    """`/mode` and a lower-cased word that names no mode."""

    word: str


ModeCommand = ModeQuestion | ModeChoice | UnknownModeWord
ChatCommand = Command | ModeCommand


CLEARED_REPLY = "Chat cleared."
STOPPED_REPLY = "Stopped."
NOTHING_TO_STOP_REPLY = "Nothing is running."
COMPACTING_REPLY = "Compacting the conversation to free up context…"
NOTHING_TO_COMPACT_REPLY = "Nothing to compact yet."
COMMANDS_LINE = "Commands: /new, /stop, /compact, /mode."
MODE_REPLY = "Mode: {name}."
MODE_USAGE = "Use /mode ask or /mode auto."
MODE_LABELS: dict[ApprovalMode, str] = {"ask": "Ask", "auto": "Auto"}


def command_words(text: str) -> tuple[str, ...]:
    """A `/word` message as its lower-cased command and the words after; `()` for any other."""
    words = text.strip().split()
    if not words or not words[0].startswith("/"):
        return ()
    # Telegram appends the bot's name in groups: `/new@my_bot`.
    return (words[0].split("@")[0].lower(), *words[1:])


def mode_command(text: str) -> ModeCommand | None:
    """The `/mode` this message asks for, read alike in every channel; `None` for any other."""
    words = command_words(text)
    if words[:1] != ("/mode",):
        return None
    if len(words) == 1:
        return ModeQuestion()
    word = words[1].lower()
    for mode in get_args(ApprovalMode):
        if word == mode:
            return ModeChoice(mode=mode)
    return UnknownModeWord(word=word)


def mode_reply(mode: ApprovalMode) -> str:
    """The line naming the mode a chat is in."""
    return MODE_REPLY.format(name=MODE_LABELS[mode])


def mode_usage_reply(mode: ApprovalMode) -> str:
    """The reply to a `/mode` that switches nothing: which words it takes, and the mode on."""
    return f"{MODE_USAGE} {mode_reply(mode)}"


async def _answer_mode_command(
    gateway: ChannelGateway, channel: str, chat_id: str, command: ModeCommand
) -> str | None:
    """Switch to the chosen mode and say so, else name the mode on; `None` for no bot."""
    match command:
        case ModeChoice(mode=mode):
            await gateway.set_approval_mode(channel, chat_id, mode)
            return mode_reply(mode)
        case ModeQuestion():
            reply_for = mode_reply
        case UnknownModeWord():
            reply_for = mode_usage_reply
    current = await gateway.approval_mode(channel, chat_id)
    return None if current is None else reply_for(current)


def unknown_skill_reply(name: str, skills: Sequence[Skill]) -> str:
    """The reply to a `/word` that is neither a command nor a skill."""
    listed = ", ".join(f"/{skill.name}" for skill in skills) or "none"
    return f"No skill named {name!r}. Skills: {listed}. {COMMANDS_LINE}"


def skills_reply(skills: Sequence[Skill]) -> str:
    """`/skills`: every skill a person may type, with what it is for."""
    if not skills:
        return f"No skills installed. {COMMANDS_LINE}"
    lines = "\n".join(f"/{skill.name} — {skill.description}" for skill in skills)
    return f"Skills you can type:\n{lines}\n\n{COMMANDS_LINE}"


async def apply_command(
    gateway: ChannelGateway, channel: str, chat_id: str, command: ChatCommand
) -> str | None:
    """Run one command, and what to say; `None`, saying nothing, for a chat linked to no bot."""
    if not await gateway.is_linked(channel, chat_id):
        return None
    if isinstance(command, ModeCommand):
        return await _answer_mode_command(gateway, channel, chat_id, command)
    if command is Command.NEW:
        await gateway.clear(channel, chat_id)
        return CLEARED_REPLY
    if command is Command.STOP:
        return STOPPED_REPLY if await gateway.stop(channel, chat_id) else NOTHING_TO_STOP_REPLY
    if command is Command.COMPACT:
        started = await gateway.compact_chat(channel, chat_id)
        return COMPACTING_REPLY if started is not None else NOTHING_TO_COMPACT_REPLY
    return skills_reply(gateway.skills.invocable())
