"""A discussion: the turn that opens it, then each member the queue says is next, as one run."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing

from harness.bots import Bot
from harness.files import ChatFile
from harness.groups import Group, GroupService
from harness.groups.domain.goal import goal_lead, goal_text
from harness.groups.domain.speaker_queue import picks_by_auto
from harness.runs.service.auto_pick import auto_pick
from harness.runs.service.goal_run import GoalOpening, goal_run
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
    runtime: Runtime,
    groups: GroupService,
    session: Session,
    text: str,
    files: tuple[ChatFile, ...],
) -> AsyncIterator[TurnEvent]:
    """A group's `/goal` run, else the turn answering `text`; `EmptyGroupError` raised now."""
    members = groups.answering(session.id)
    group = members.group
    goal = goal_text(text)
    lead = None if group is None or goal is None else goal_lead(goal, members.bots, group)
    if goal is not None and lead is not None:
        return goal_run(runtime, groups, session, GoalOpening(text, files, goal, lead))
    if group is not None and picks_by_auto(text, members.bots, group):
        return _auto_picked_turn(runtime, groups, session, group, text, files)
    return _answered(runtime, session, groups.first_speaker(session, text, None), text, files)


async def _auto_picked_turn(
    runtime: Runtime,
    groups: GroupService,
    session: Session,
    group: Group,
    text: str,
    files: tuple[ChatFile, ...],
) -> AsyncIterator[TurnEvent]:
    """Auto's pick logged, then the turn its first speaker answers `text` in."""
    try:
        members = groups.answering(session.id).bots
        pick = await auto_pick(runtime.models, session, group, members, text)
    except asyncio.CancelledError:
        _log_unanswered(runtime, session, text, files)
        raise
    session.append(pick)
    speaker = groups.first_speaker(session, text, pick)
    async with aclosing(_answered(runtime, session, speaker, text, files)) as events:
        async for event in events:
            yield event


def _answered(
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
    _log_unanswered(runtime, session, text, files)
    return
    yield


def _log_unanswered(
    runtime: Runtime, session: Session, text: str, files: tuple[ChatFile, ...]
) -> None:
    turn = max(session.next_turn() - 1, 0)
    runtime.log_person_message(session, text, files, turn=turn, sees_images=False)


def _next_turn(
    runtime: Runtime, groups: GroupService, session: Session
) -> AsyncIterator[TurnEvent] | None:
    """The next speaker's turn, its instructions logged first; `None` when nobody is next."""
    speaker = groups.next_speaker(session)
    if speaker is None:
        return None
    return runtime.speak(session=session, bot_id=speaker.id)
