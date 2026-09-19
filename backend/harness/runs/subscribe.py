"""Reading a run's log from a cursor, live."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import partial

from harness.runs.store import Run
from harness.session.models import SessionEvent


async def subscribe(run: Run, *, after: int) -> AsyncIterator[SessionEvent]:
    """Every event past `after`, then each new one, until the turn ends."""
    cursor = after
    while True:
        async with run.condition:
            await run.condition.wait_for(partial(_caught_up, run, cursor))
            events = list(run.session.events()[cursor:])
            settled = run.settled

        for event in events:
            yield event
        cursor += len(events)

        if settled and cursor >= len(run.session.events()):
            return


def _caught_up(run: Run, cursor: int) -> bool:
    return len(run.session.events()) > cursor or run.settled
