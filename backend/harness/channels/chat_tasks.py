"""One background task per chat, held strongly."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import NamedTuple


class ChatKey(NamedTuple):
    channel: str
    chat_id: str


class ChatTasks:
    """The running task for each chat, if it has one."""

    def __init__(self) -> None:
        self._tasks: dict[ChatKey, asyncio.Task[None]] = {}

    def start(self, key: ChatKey, work: Coroutine[None, None, None]) -> None:
        """Run `work` as this chat's task."""
        task = asyncio.create_task(work)
        self._tasks[key] = task
        task.add_done_callback(lambda done: self._forget(key, done))

    def get(self, key: ChatKey) -> asyncio.Task[None] | None:
        return self._tasks.get(key)

    def __bool__(self) -> bool:
        return bool(self._tasks)

    def running(self) -> bool:
        """Whether any chat's task is still running — for tests waiting on idle."""
        return any(not task.done() for task in self._tasks.values())

    async def aclose(self) -> None:
        """Cancel every task and wait for each to finish."""
        for task in list(self._tasks.values()):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    def _forget(self, key: ChatKey, task: asyncio.Task[None]) -> None:
        if self._tasks.get(key) is task:
            del self._tasks[key]
