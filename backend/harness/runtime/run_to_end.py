"""A copy of a runtime run to its end in a session of its own, for subagents and workers."""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass

from harness.runtime.events import TurnEvent
from harness.runtime.inbox import NO_INBOX
from harness.runtime.service import Runtime
from harness.session.domain.log import Session
from harness.session.service import SessionService
from harness.tools import Approval, Failure, Ok


@dataclass(frozen=True)
class HelperTurn:
    """One turn of a copy: the intro put before its guidance, its prompt, and the bot it is for."""

    intro: str
    prompt: str
    bot_id: str


@dataclass(frozen=True)
class HelperAnswer:
    """The person's answer to a copy's waiting call: the intro, the call, the answer, the bot."""

    intro: str
    call_id: str
    outcome: Ok | Failure | Approval
    bot_id: str


async def run_to_end(
    runtime: Runtime, sessions: SessionService, session: Session, turn: HelperTurn
) -> TurnEvent | None:
    """Run `turn` on a copy of `runtime` in `session`, flushed by `sessions`; its last event."""
    copy = _copy(runtime, sessions, turn.intro)
    return await _last(
        sessions, session, copy.run(turn.prompt, session=session, bot_id=turn.bot_id)
    )


async def resume_to_end(
    runtime: Runtime, sessions: SessionService, session: Session, answer: HelperAnswer
) -> TurnEvent | None:
    """Answer the call `answer` names on a copy of `runtime` in `session`; the turn's last event."""
    copy = _copy(runtime, sessions, answer.intro)
    resumed = copy.resume(answer.call_id, answer.outcome, session=session, bot_id=answer.bot_id)
    return await _last(sessions, session, resumed)


def _copy(runtime: Runtime, sessions: SessionService, intro: str) -> Runtime:
    return dataclasses.replace(
        runtime, guidance=intro + runtime.guidance, checkpoint=sessions.flush, inbox=NO_INBOX
    )


async def _last(
    sessions: SessionService, session: Session, turn: AsyncGenerator[TurnEvent]
) -> TurnEvent | None:
    """`turn` drained, `session` flushed whatever happens: the last event it yielded."""
    last: TurnEvent | None = None
    try:
        async with aclosing(turn) as events:
            async for event in events:
                last = event
    finally:
        await sessions.flush(session)
    return last
