"""What happened in the app outside any one chat's log, and who is listening for it."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TurnStarted(BaseModel):
    """A turn began in this chat."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    type: Literal["chat/turn-started"] = "chat/turn-started"
    chat_id: str


class BotsChanged(BaseModel):
    """The bots or groups were written."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    type: Literal["bots/changed"] = "bots/changed"


AppEvent = TurnStarted | BotsChanged


class AppEvents:
    """The app's publisher: every open subscriber's queue, and what is published into them."""

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
