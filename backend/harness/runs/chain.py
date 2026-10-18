"""A discussion: the turn that opens it, then each member the queue says is next, as one run."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing

from harness.bots import BotService
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.log import Session


async def discussion_events(
    runtime: Runtime, bots: BotService, session: Session, opening: AsyncIterator[TurnEvent]
) -> AsyncIterator[TurnEvent]:
    """`opening`'s events, then each next speaker's, until nobody is next or a turn stops short."""
    turn: AsyncIterator[TurnEvent] | None = opening
    while turn is not None:
        terminal: TurnEvent | None = None
        async with aclosing(turn) as events:
            async for event in events:
                terminal = event
                yield event
        turn = _next_turn(runtime, bots, session) if isinstance(terminal, AgentCompleted) else None


def _next_turn(
    runtime: Runtime, bots: BotService, session: Session
) -> AsyncIterator[TurnEvent] | None:
    """The next speaker's turn, its instructions logged first; `None` when nobody is next."""
    speaker = bots.next_speaker(session)
    if speaker is None:
        return None
    return runtime.speak(session=session, bot_id=speaker.id)
