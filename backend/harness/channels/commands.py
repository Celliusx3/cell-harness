"""The slash commands a chat accepts, and what they say back."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from harness.channels.gateway import ChannelGateway
from harness.skills import Skill
from harness.tools import ApprovalMode


class Command(StrEnum):
    """What a platform decided the user asked for."""

    NEW = "new"
    STOP = "stop"
    SKILLS = "skills"
    COMPACT = "compact"


@dataclass(frozen=True)
class ModeCommand:
    """`/mode` and the lower-cased word after it; `""` when none."""

    word: str


ChatCommand = Command | ModeCommand


CLEARED = "Chat cleared."
STOPPED = "Stopped."
NOTHING_TO_STOP = "Nothing is running."
COMPACTING = "Compacting the conversation to free up context…"
NOTHING_TO_COMPACT = "Nothing to compact yet."
COMMANDS = "Commands: /new, /stop, /compact, /mode."
MODE_IS = "Mode: {name}."
MODE_WORDS = "Use /mode ask or /mode auto."
MODE_NAMES: dict[ApprovalMode, str] = {"ask": "Ask", "auto": "Auto"}
_MODE_OF_WORD: dict[str, ApprovalMode] = {"ask": "ask", "auto": "auto"}


def slash_words(text: str) -> tuple[str, ...]:
    """A `/word` message as its lower-cased command and the words after; `()` for any other."""
    words = text.strip().split()
    if not words or not words[0].startswith("/"):
        return ()
    # Telegram appends the bot's name in groups: `/new@my_bot`.
    return (words[0].split("@")[0].lower(), *words[1:])


def mode_command(text: str) -> ModeCommand | None:
    """The `/mode` this message asks for, read alike in every channel; `None` for any other."""
    words = slash_words(text)
    if words[:1] != ("/mode",):
        return None
    return ModeCommand(word=words[1].lower() if len(words) > 1 else "")


def mode_named(word: str) -> ApprovalMode | None:
    """The mode `/mode <word>` switches to; `None` for a word that names none."""
    return _MODE_OF_WORD.get(word)


def mode_is(mode: ApprovalMode) -> str:
    """The line naming the mode a chat is in."""
    return MODE_IS.format(name=MODE_NAMES[mode])


def mode_words(mode: ApprovalMode) -> str:
    """The reply to a `/mode` that switches nothing: which words it takes, and the mode on."""
    return f"{MODE_WORDS} {mode_is(mode)}"


async def _mode_reply(gateway: ChannelGateway, channel: str, chat_id: str, word: str) -> str | None:
    """Switch to the mode `word` names and say so, else name the mode on; `None` for no bot."""
    chosen = mode_named(word)
    if chosen is not None:
        await gateway.set_mode(channel, chat_id, chosen)
        return mode_is(chosen)
    current = await gateway.mode_of(channel, chat_id)
    if current is None:
        return None
    return mode_is(current) if not word else mode_words(current)


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


async def apply(
    gateway: ChannelGateway, channel: str, chat_id: str, command: ChatCommand
) -> str | None:
    """Run one command, and what to say; `None`, saying nothing, for a chat linked to no bot."""
    if not await gateway.is_linked(channel, chat_id):
        return None
    if isinstance(command, ModeCommand):
        return await _mode_reply(gateway, channel, chat_id, command.word)
    if command is Command.NEW:
        await gateway.clear(channel, chat_id)
        return CLEARED
    if command is Command.STOP:
        return STOPPED if await gateway.stop(channel, chat_id) else NOTHING_TO_STOP
    if command is Command.COMPACT:
        started = await gateway.compact_chat(channel, chat_id)
        return COMPACTING if started is not None else NOTHING_TO_COMPACT
    return skills_reply(gateway.skills.invocable())
