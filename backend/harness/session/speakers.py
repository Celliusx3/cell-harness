"""Which bot spoke each turn, folded out of the log."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from harness.session.models import SessionEvent, TurnStart


def turn_speakers(events: Sequence[SessionEvent]) -> Mapping[int, str]:
    """Each turn whose `turn/start` names a bot, mapped to that bot's id."""
    return {
        event.turn: event.bot_id
        for event in events
        if isinstance(event, TurnStart) and event.bot_id is not None
    }


def last_speaker(events: Sequence[SessionEvent]) -> str | None:
    """The bot that opened the last turn; `None` when it names none or no turn was opened."""
    for event in reversed(events):
        if isinstance(event, TurnStart):
            return event.bot_id
    return None
