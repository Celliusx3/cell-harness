"""Who speaks next in a chat: the person's mentions queue its bots, and theirs join the queue."""

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
MAX_TURNS_FROM_MENTIONS = 6


class SpeakerQueue(NamedTuple):
    """The members waiting to speak, in order, and how many turns mentions have added."""

    waiting: tuple[Bot, ...]
    turns_from_mentions: int


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


def first_speakers(text: str, members: Sequence[Bot]) -> tuple[Bot, ...]:
    """Who answers the person's `text`: the members it mentions; all for @everyone or nobody."""
    invoked = display(text)
    typed = text if invoked is None else invoked.typed
    named = mentioned_members(typed, members)
    if not named or is_mentioned(typed, EVERYONE):
        return tuple(members)
    return named


def next_speaker(events: Sequence[SessionEvent], members: Sequence[Bot]) -> Bot | None:
    """The head of the queue once the log's last turn completed; `None` when nobody is next."""
    queue = SpeakerQueue((), 0)
    speaker_id: str | None = None
    said: tuple[str, ...] = ()
    completed = False
    for event in events:
        if isinstance(event, UserMessageEvent):
            queue, said = SpeakerQueue(first_speakers(event.message.content, members), 0), ()
        elif isinstance(event, TurnStart):
            speaker_id, completed = event.bot_id, False
        elif isinstance(event, AssistantMessageEvent):
            said = (*said, event.message.content)
        elif isinstance(event, TurnEnd):
            completed = event.reason == "completed"
            if completed:
                queue, said = _queue_after(queue, speaker_id, "\n\n".join(said), members), ()
    return queue.waiting[0] if completed and queue.waiting else None


def _queue_after(
    queue: SpeakerQueue, speaker_id: str | None, said: str, members: Sequence[Bot]
) -> SpeakerQueue:
    waiting = tuple(bot for bot in queue.waiting if bot.id != speaker_id)
    ids = {bot.id for bot in waiting} | {speaker_id}
    joining = tuple(bot for bot in mentioned_members(said, members) if bot.id not in ids)
    taken = joining[: MAX_TURNS_FROM_MENTIONS - queue.turns_from_mentions]
    return SpeakerQueue((*waiting, *taken), queue.turns_from_mentions + len(taken))
