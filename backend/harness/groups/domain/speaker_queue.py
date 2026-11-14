"""The speaker queue of a chat: the person's mentions fill it, and a speaker's join it."""

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

    @classmethod
    def after_message(cls, text: str, members: Sequence[Bot]) -> SpeakerQueue:
        """The queue the person's `text` starts: the members it mentions, or all of them."""
        invoked = typed_invocation(text)
        typed = text if invoked is None else invoked.typed
        named = tuple(bot for bot in members if bot.is_mentioned_in(typed))
        everyone = not named or EVERYONE_MENTION.search(typed) is not None
        return cls(tuple(members) if everyone else named, 0)

    @classmethod
    def next_in(cls, events: Sequence[SessionEvent], members: Sequence[Bot]) -> Bot | None:
        """The member who speaks once the log's last turn completed; `None` when nobody is next."""
        queue = cls((), 0)
        speaker_id: str | None = None
        replies: tuple[str, ...] = ()
        completed = False
        for event in events:
            if isinstance(event, UserMessageEvent):
                queue, replies = cls.after_message(event.message.content, members), ()
            elif isinstance(event, TurnStart):
                speaker_id, completed = event.bot_id, False
            elif isinstance(event, AssistantMessageEvent):
                replies = (*replies, event.message.content)
            elif isinstance(event, TurnEnd):
                completed = event.reason == "completed"
                if completed:
                    queue = queue.after_turn(speaker_id, "\n\n".join(replies), members)
                    replies = ()
        return queue.waiting[0] if completed and queue.waiting else None

    def after_turn(self, speaker_id: str | None, said: str, members: Sequence[Bot]) -> SpeakerQueue:
        """This queue once the speaker has left it and the members `said` mentions have joined."""
        waiting = tuple(bot for bot in self.waiting if bot.id != speaker_id)
        ids = {bot.id for bot in waiting} | {speaker_id}
        joining = tuple(bot for bot in members if bot.is_mentioned_in(said) and bot.id not in ids)
        taken = joining[: MAX_TURNS_FROM_MENTIONS - self.turns_from_mentions]
        return SpeakerQueue((*waiting, *taken), self.turns_from_mentions + len(taken))
