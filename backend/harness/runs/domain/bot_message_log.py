"""What a chat's log says about the bot messages in it: the hop it reached, the reply it gave."""

from __future__ import annotations

from collections.abc import Sequence

from harness.prompts import BOT_DID_NOT_FINISH, BOT_WAITING_ON_USER
from harness.session.domain.models import (
    AssistantMessageEvent,
    BotMessageEvent,
    SessionEvent,
    TurnEnd,
    TurnEndReason,
    TurnStart,
)

MAX_HOPS = 6


def hop_of_last_turn(events: Sequence[SessionEvent]) -> int:
    """The hop of the bot message that opened the last turn; 0 when no bot message did."""
    hop = 0
    for event in events:
        if isinstance(event, TurnStart):
            hop = 0
        elif isinstance(event, BotMessageEvent):
            hop = event.message.hop
    return hop


def final_reply(events: Sequence[SessionEvent], name: str) -> str:
    """What the last turn ended by saying when it completed; else why `name` has no answer."""
    said = ""
    reason: TurnEndReason | None = None
    for event in events:
        if isinstance(event, TurnStart):
            said, reason = "", None
        elif isinstance(event, AssistantMessageEvent):
            said = event.message.content
        elif isinstance(event, TurnEnd):
            reason = event.reason
    if reason == "completed":
        return said
    if reason == "pending":
        return BOT_WAITING_ON_USER.format(name=name)
    return BOT_DID_NOT_FINISH.format(name=name)
