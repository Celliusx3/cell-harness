"""A copy of a runtime run to its end in a session of its own, for subagents and workers."""

from __future__ import annotations

import dataclasses
from contextlib import aclosing
from dataclasses import dataclass

from harness.runtime.events import TurnEvent
from harness.runtime.inbox import NO_INBOX
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.service import SessionService


@dataclass(frozen=True)
class HelperTurn:
    """One turn of a copy: the intro put before its guidance, its prompt, and the bot it is for."""

    intro: str
    prompt: str
    bot_id: str


async def run_to_end(
    runtime: Runtime, sessions: SessionService, session: Session, turn: HelperTurn
) -> TurnEvent | None:
    """Run `turn` on a copy of `runtime` in `session`, flushed by `sessions`; its last event."""
    copy = dataclasses.replace(
        runtime, guidance=turn.intro + runtime.guidance, checkpoint=sessions.flush, inbox=NO_INBOX
    )
    last: TurnEvent | None = None
    try:
        async with aclosing(copy.run(turn.prompt, session=session, bot_id=turn.bot_id)) as events:
            async for event in events:
                last = event
    finally:
        await sessions.flush(session)
    return last
