"""Reading a run's log from a cursor, live."""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import partial

from harness.runs.service import Run
from harness.session.log import Numbered


async def subscribe(run: Run, *, after: int) -> AsyncIterator[Numbered]:
    """Every event numbered `after` and up, then each new one, until the turn ends."""
    cursor = after
    while True:
        async with run.condition:
            await run.condition.wait_for(partial(_caught_up, run, cursor))
            items = run.session.numbered_events_from(cursor)
            settled = run.settled

        for item in items:
            yield item
        if items:
            cursor = items[-1].number + 1

        if settled and cursor >= run.session.next_number():
            return


def _caught_up(run: Run, cursor: int) -> bool:
    return run.session.next_number() > cursor or run.settled
