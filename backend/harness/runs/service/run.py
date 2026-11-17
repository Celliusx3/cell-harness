"""`Run`: one turn in flight, the log it writes into, and how a caller waits for it to settle."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from functools import partial

from harness.session.domain.log import NumberedEvent, Session


class Run:
    """One turn in flight, the log it is writing into, and the tasks that drive and settle it."""

    def __init__(self, session: Session, first_event_number: int) -> None:
        self.session = session
        self.first_event_number = first_event_number
        self.error: Exception | None = None
        self.turn_task: asyncio.Task[None] | None = None
        self.settle_task: asyncio.Task[None] | None = None
        self._is_settled = False
        self._condition = asyncio.Condition()

    @property
    def is_settled(self) -> bool:
        """Whether the turn has ended and its log is made durable."""
        return self._is_settled

    async def wake(self) -> None:
        """Tell everyone reading this run that its log grew."""
        async with self._condition:
            self._condition.notify_all()

    async def mark_settled(self) -> None:
        """Mark the turn ended, and release everyone waiting on it."""
        async with self._condition:
            self._is_settled = True
            self._condition.notify_all()

    async def end(self) -> None:
        """Cancel the turn, if it has begun, and wait for the run to settle."""
        if self.turn_task is not None:
            self.turn_task.cancel()
        if self.settle_task is not None:
            await asyncio.shield(self.settle_task)

    async def wait_until_settled(self) -> None:
        """Wait until this run has settled."""
        async with self._condition:
            await self._condition.wait_for(lambda: self._is_settled)

    async def events_from(self, after: int) -> AsyncIterator[NumberedEvent]:
        """Every event numbered `after` and up, then each new one, until the turn ends."""
        cursor = after
        while True:
            async with self._condition:
                await self._condition.wait_for(partial(self._has_news_or_settled, cursor))
                items = self.session.numbered_events_from(cursor)
                settled = self._is_settled
            for item in items:
                yield item
            if items:
                cursor = items[-1].number + 1
            if settled and cursor >= self.session.next_number():
                return

    def _has_news_or_settled(self, cursor: int) -> bool:
        return self.session.next_number() > cursor or self._is_settled
