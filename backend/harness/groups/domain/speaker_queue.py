"""The speaker queue of a chat: the person's message fills it, and those it asks bring others in."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

from harness.bots.domain.models import MENTION_PATTERN, Bot
from harness.groups.domain.models import Group
from harness.session.domain.models import (
    AssistantMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.skills.domain.invocation import typed_invocation

EVERYONE_MENTION = re.compile(MENTION_PATTERN.format(name="everyone"), re.IGNORECASE)


class SpeakerQueue(NamedTuple):
    """Who waits to speak, who the person's message asked, and who a mention already brought in."""

    waiting: tuple[Bot, ...]
    asked_ids: frozenset[str]
    joined_ids: frozenset[str]

    @classmethod
    def after_message(cls, text: str, members: Sequence[Bot], group: Group | None) -> SpeakerQueue:
        """The queue `text` starts: all for @everyone, else those it names, else `group`'s reply."""
        invoked = typed_invocation(text)
        typed = text if invoked is None else invoked.typed
        if EVERYONE_MENTION.search(typed) is not None:
            return cls._asking(tuple(members))
        named = tuple(bot for bot in members if bot.is_mentioned_in(typed))
        return cls._asking(named or _answering_unnamed(members, group))

    @classmethod
    def next_in(
        cls, events: Sequence[SessionEvent], members: Sequence[Bot], group: Group | None
    ) -> Bot | None:
        """The member who speaks once the log's last turn completed; `None` when nobody is next."""
        queue = cls((), frozenset(), frozenset())
        speaker_id: str | None = None
        replies: tuple[str, ...] = ()
        completed = False
        for event in events:
            if isinstance(event, UserMessageEvent):
                queue, replies = cls.after_message(event.message.content, members, group), ()
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

    @classmethod
    def _asking(cls, members: tuple[Bot, ...]) -> SpeakerQueue:
        return cls(members, frozenset(bot.id for bot in members), frozenset())

    def after_turn(self, speaker_id: str | None, said: str, members: Sequence[Bot]) -> SpeakerQueue:
        """This queue without the speaker; if the person asked it, those it names join once each."""
        waiting = tuple(bot for bot in self.waiting if bot.id != speaker_id)
        if speaker_id not in self.asked_ids:
            return self._replace(waiting=waiting)
        ids = {bot.id for bot in waiting} | {speaker_id} | self.joined_ids
        joining = tuple(bot for bot in members if bot.is_mentioned_in(said) and bot.id not in ids)
        joined = self.joined_ids | {bot.id for bot in joining}
        return SpeakerQueue((*waiting, *joining), self.asked_ids, joined)


def _answering_unnamed(members: Sequence[Bot], group: Group | None) -> tuple[Bot, ...]:
    """Who answers a message naming nobody: every member, the lead or else the first, or none."""
    if group is None or group.reply == "everyone":
        return tuple(members)
    if group.reply == "mentions":
        return ()
    lead = next((bot for bot in members if bot.id == group.lead_id), None)
    return (lead,) if lead is not None else tuple(members[:1])
