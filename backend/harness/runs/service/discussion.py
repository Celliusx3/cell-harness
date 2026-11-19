"""A discussion: the turn that opens it, then each member the queue says is next, as one run."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing

from harness.bots import Bot
from harness.files import ChatFile
from harness.groups import GroupService
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.domain.log import Session


async def discussion_events(
    runtime: Runtime, groups: GroupService, session: Session, opening: AsyncIterator[TurnEvent]
) -> AsyncIterator[TurnEvent]:
    """`opening`'s events, then each next speaker's, until nobody is next or a turn stops short."""
    turn: AsyncIterator[TurnEvent] | None = opening
    while turn is not None:
        terminal: TurnEvent | None = None
        async with aclosing(turn) as events:
            async for event in events:
                terminal = event
                yield event
        turn = (
            _next_turn(runtime, groups, session) if isinstance(terminal, AgentCompleted) else None
        )


def opening_turn(
    runtime: Runtime, session: Session, speaker: Bot | None, text: str, files: tuple[ChatFile, ...]
) -> AsyncIterator[TurnEvent]:
    """The turn `speaker` answers the person's `text` in; just `text` logged if nobody is asked."""
    if speaker is None:
        return _unanswered_message(runtime, session, text, files)
    return runtime.run(text, session=session, bot_id=speaker.id, files=files)


async def _unanswered_message(
    runtime: Runtime, session: Session, text: str, files: tuple[ChatFile, ...]
) -> AsyncIterator[TurnEvent]:
    """The person's `text` logged in the last turn, opening none: nobody was asked to answer it."""
    turn = max(session.next_turn() - 1, 0)
    runtime.log_person_message(session, text, files, turn=turn, sees_images=False)
    return
    yield


def _next_turn(
    runtime: Runtime, groups: GroupService, session: Session
) -> AsyncIterator[TurnEvent] | None:
    """The next speaker's turn, its instructions logged first; `None` when nobody is next."""
    speaker = groups.next_speaker(session)
    if speaker is None:
        return None
    return runtime.speak(session=session, bot_id=speaker.id)
