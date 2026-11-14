"""Turn order in a chat: the person's mentions queue its bots, and theirs join the queue."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple, Protocol

from harness.bots.domain.models import Bot
from harness.session.domain.models import (
    AssistantMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.skills.domain.invocation import display

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


class TurnOrder(Protocol):
    """Who in a chat answers the person first, and who speaks after each turn."""

    def first_speakers(self, text: str, members: Sequence[Bot]) -> tuple[Bot, ...]:
        """Who answers the person's `text`, in order."""
        ...

    def next_speaker(self, events: Sequence[SessionEvent], members: Sequence[Bot]) -> Bot | None:
        """Who speaks once the log's last turn ends; `None` when nobody is next."""
        ...


class MentionTurnOrder:
    """Mentions pick the speakers: the person's queue them, a speaker's add up to a cap."""

    def __init__(self, *, max_turns_from_mentions: int) -> None:
        self._max_turns_from_mentions = max_turns_from_mentions

    def first_speakers(self, text: str, members: Sequence[Bot]) -> tuple[Bot, ...]:
        """The members the person's `text` mentions; all of them for @everyone or nobody."""
        invoked = display(text)
        typed = text if invoked is None else invoked.typed
        named = mentioned_members(typed, members)
        if not named or is_mentioned(typed, EVERYONE):
            return tuple(members)
        return named

    def next_speaker(self, events: Sequence[SessionEvent], members: Sequence[Bot]) -> Bot | None:
        """The head of the queue once the log's last turn completed; `None` when nobody is next."""
        queue = SpeakerQueue((), 0)
        speaker_id: str | None = None
        replies: tuple[str, ...] = ()
        completed = False
        for event in events:
            if isinstance(event, UserMessageEvent):
                first = self.first_speakers(event.message.content, members)
                queue, replies = SpeakerQueue(first, 0), ()
            elif isinstance(event, TurnStart):
                speaker_id, completed = event.bot_id, False
            elif isinstance(event, AssistantMessageEvent):
                replies = (*replies, event.message.content)
            elif isinstance(event, TurnEnd):
                completed = event.reason == "completed"
                if completed:
                    queue = self._queue_after(queue, speaker_id, "\n\n".join(replies), members)
                    replies = ()
        return queue.waiting[0] if completed and queue.waiting else None

    def _queue_after(
        self, queue: SpeakerQueue, speaker_id: str | None, said: str, members: Sequence[Bot]
    ) -> SpeakerQueue:
        waiting = tuple(bot for bot in queue.waiting if bot.id != speaker_id)
        ids = {bot.id for bot in waiting} | {speaker_id}
        joining = tuple(bot for bot in mentioned_members(said, members) if bot.id not in ids)
        taken = joining[: self._max_turns_from_mentions - queue.turns_from_mentions]
        return SpeakerQueue((*waiting, *taken), queue.turns_from_mentions + len(taken))


MENTION_TURN_ORDER = MentionTurnOrder(max_turns_from_mentions=MAX_TURNS_FROM_MENTIONS)
