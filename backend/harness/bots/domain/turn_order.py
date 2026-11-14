"""Turn order in a chat: the person's mentions queue its bots, and theirs join the queue."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

from harness.bots.domain.models import MENTION_PATTERN, Bot
from harness.session.domain.models import (
    AssistantMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.skills.domain.invocation import typed_invocation

EVERYONE_MENTION = re.compile(MENTION_PATTERN.format(name="everyone"), re.IGNORECASE)
MAX_TURNS_FROM_MENTIONS = 6


class SpeakerQueue(NamedTuple):
    """The members waiting to speak, in order, and how many turns mentions have added."""

    waiting: tuple[Bot, ...]
    turns_from_mentions: int

    def after_turn(
        self,
        speaker_id: str | None,
        said: str,
        members: Sequence[Bot],
        max_turns_from_mentions: int,
    ) -> SpeakerQueue:
        """This queue once the speaker has left it and the members `said` mentions have joined."""
        waiting = tuple(bot for bot in self.waiting if bot.id != speaker_id)
        ids = {bot.id for bot in waiting} | {speaker_id}
        joining = tuple(bot for bot in members if bot.is_mentioned_in(said) and bot.id not in ids)
        taken = joining[: max_turns_from_mentions - self.turns_from_mentions]
        return SpeakerQueue((*waiting, *taken), self.turns_from_mentions + len(taken))


class MentionTurnOrder:
    """Mentions pick the speakers: the person's queue them, a speaker's add up to a cap."""

    def __init__(self, *, max_turns_from_mentions: int) -> None:
        self._max_turns_from_mentions = max_turns_from_mentions

    def first_speakers(self, text: str, members: Sequence[Bot]) -> tuple[Bot, ...]:
        """The members the person's `text` mentions; all of them for @everyone or nobody."""
        invoked = typed_invocation(text)
        typed = text if invoked is None else invoked.typed
        named = tuple(bot for bot in members if bot.is_mentioned_in(typed))
        if not named or EVERYONE_MENTION.search(typed) is not None:
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
                    queue = queue.after_turn(
                        speaker_id, "\n\n".join(replies), members, self._max_turns_from_mentions
                    )
                    replies = ()
        return queue.waiting[0] if completed and queue.waiting else None


MENTION_TURN_ORDER = MentionTurnOrder(max_turns_from_mentions=MAX_TURNS_FROM_MENTIONS)
