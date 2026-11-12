"""The app's publisher: every open subscriber's queue, and what is published into them."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from harness.app_events.models import AppEvent


class AppEventService:
    """Publishes each app event to every open subscriber."""

    def __init__(self) -> None:
        self._queues: tuple[asyncio.Queue[AppEvent], ...] = ()

    def publish(self, event: AppEvent) -> None:
        """Put `event` on every open subscriber's queue."""
        for queue in self._queues:
            queue.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[AppEvent]:
        """Every event published from now on, until the reader stops."""
        queue: asyncio.Queue[AppEvent] = asyncio.Queue()
        self._queues = (*self._queues, queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._queues = tuple(held for held in self._queues if held is not queue)
