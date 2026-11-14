"""`Run` — one turn in flight, and how a caller waits for it to settle."""

from __future__ import annotations

import asyncio

from harness.session.domain.log import Session


class RunAlreadyActiveError(RuntimeError):
    """This conversation is already running a turn."""


class Run:
    """One turn in flight, and the log it is writing into."""

    def __init__(self, session: Session, first_event_number: int) -> None:
        self.session = session
        self.first_event_number = first_event_number
        self.is_settled = False
        self.error: Exception | None = None
        self.condition = asyncio.Condition()
        self._turn_task: asyncio.Task[None] | None = None
        self._settle_task: asyncio.Task[None] | None = None


async def wait_until_settled(run: Run) -> None:
    """Wait until `run` has settled."""
    async with run.condition:
        await run.condition.wait_for(lambda: run.is_settled)
