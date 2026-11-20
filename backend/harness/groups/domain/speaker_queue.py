"""The speaker queue of a chat: the person's message fills it, and those it asks bring others in."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

from harness.bots.domain.models import MENTION_PATTERN, Bot
from harness.groups.domain.models import Group
from harness.session.domain.models import (
    AssistantMessageEvent,
    GoalStartEvent,
    GroupAutoPickEvent,
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
    def after_message(
        cls,
        text: str,
        members: Sequence[Bot],
        group: Group | None,
        pick: GroupAutoPickEvent | None,
    ) -> SpeakerQueue:
        """The queue `text` starts: all for @everyone, else those it names, else `group`'s reply."""
        typed = _typed(text)
        if EVERYONE_MENTION.search(typed) is not None:
            return cls._asking(tuple(members))
        named = tuple(bot for bot in members if bot.is_mentioned_in(typed))
        return cls._asking(named or _answering_unnamed(members, group, pick))

    @classmethod
    def next_in(
        cls, events: Sequence[SessionEvent], members: Sequence[Bot], group: Group | None
    ) -> Bot | None:
        """The member who speaks once the log's last turn completed; nobody after a `/goal`."""
        queue = cls((), frozenset(), frozenset())
        speaker_id: str | None = None
        replies: tuple[str, ...] = ()
        completed = False
        choices: dict[int, GroupAutoPickEvent | GoalStartEvent] = {}
        for event in events:
            if isinstance(event, (GroupAutoPickEvent, GoalStartEvent)):
                choices[event.turn] = event
            elif isinstance(event, UserMessageEvent):
                queue, replies = cls._after(event, members, group, choices.get(event.turn)), ()
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
    def _after(
        cls,
        message: UserMessageEvent,
        members: Sequence[Bot],
        group: Group | None,
        pick: GroupAutoPickEvent | GoalStartEvent | None,
    ) -> SpeakerQueue:
        """The queue the person's `message` starts; empty when it started a goal run."""
        if isinstance(pick, GoalStartEvent):
            return cls._asking(())
        return cls.after_message(message.message.content, members, group, pick)

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


def picks_by_auto(text: str, members: Sequence[Bot], group: Group) -> bool:
    """Whether `group` is on Auto and `text` names neither a member nor everyone."""
    if group.reply != "auto":
        return False
    typed = _typed(text)
    named = any(bot.is_mentioned_in(typed) for bot in members)
    return not named and EVERYONE_MENTION.search(typed) is None


def lead_of(members: Sequence[Bot], group: Group) -> Bot | None:
    """`group`'s lead while it is an active member, else the first member; `None` for none."""
    lead = next((bot for bot in members if bot.id == group.lead_id), None)
    return lead if lead is not None else next(iter(members), None)


def _typed(text: str) -> str:
    invoked = typed_invocation(text)
    return text if invoked is None else invoked.typed


def _answering_unnamed(
    members: Sequence[Bot], group: Group | None, pick: GroupAutoPickEvent | None
) -> tuple[Bot, ...]:
    """Who answers a message naming nobody: everyone, nobody, Auto's pick, else the lead."""
    if group is None or group.reply == "everyone":
        return tuple(members)
    if group.reply == "mentions":
        return ()
    if group.reply == "auto" and pick is not None:
        picked = tuple(bot for bot in members if pick.bot_id in (None, bot.id))
        if picked:
            return picked
    lead = lead_of(members, group)
    return () if lead is None else (lead,)
