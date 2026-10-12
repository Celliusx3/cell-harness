"""Who speaks next in a chat: the person's mentions line its bots up, and theirs join the line."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

from harness.bots.models import Bot
from harness.session.models import (
    AssistantMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.skills.invocation import display

EVERYONE = "everyone"
MENTION_TURNS = 6


class Line(NamedTuple):
    """The members waiting to speak, in order, and how many turns mentions have added."""

    waiting: tuple[Bot, ...]
    added: int


def is_mentioned(text: str, name: str) -> bool:
    """Whether `text` holds `@name` in any case, not inside a longer word or name."""
    wanted = name.strip()
    if not wanted:
        return False
    pattern = rf"(?:^|[^\w-])@{re.escape(wanted)}(?![\w-])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def mentioned_members(text: str, members: Sequence[Bot]) -> tuple[Bot, ...]:
    """The members `text` mentions, in member order."""
    return tuple(bot for bot in members if is_mentioned(text, bot.name))


def first_line(text: str, members: Sequence[Bot]) -> tuple[Bot, ...]:
    """Who answers the person's `text`: the members it mentions; all for @everyone or nobody."""
    invoked = display(text)
    typed = text if invoked is None else invoked.typed
    named = mentioned_members(typed, members)
    if not named or is_mentioned(typed, EVERYONE):
        return tuple(members)
    return named


def next_speaker(events: Sequence[SessionEvent], members: Sequence[Bot]) -> Bot | None:
    """The head of the line once the log's last turn completed; `None` when nobody is next."""
    line = Line((), 0)
    speaker: str | None = None
    said: tuple[str, ...] = ()
    completed = False
    for event in events:
        if isinstance(event, UserMessageEvent):
            line, said = Line(first_line(event.message.content, members), 0), ()
        elif isinstance(event, TurnStart):
            speaker, completed = event.bot_id, False
        elif isinstance(event, AssistantMessageEvent):
            said = (*said, event.message.content)
        elif isinstance(event, TurnEnd):
            completed = event.reason == "completed"
            if completed:
                line, said = _line_after(line, speaker, "\n\n".join(said), members), ()
    return line.waiting[0] if completed and line.waiting else None


def _line_after(line: Line, speaker: str | None, said: str, members: Sequence[Bot]) -> Line:
    """`line` without `speaker`, then each member it mentioned who is not waiting, up to the cap."""
    waiting = tuple(bot for bot in line.waiting if bot.id != speaker)
    ids = {bot.id for bot in waiting} | {speaker}
    joining = tuple(bot for bot in mentioned_members(said, members) if bot.id not in ids)
    taken = joining[: MENTION_TURNS - line.added]
    return Line((*waiting, *taken), line.added + len(taken))
