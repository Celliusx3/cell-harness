"""One background task per chat, held strongly.

The gateway starts one when a turn begins — it delivers the reply and then
starts whatever queued behind it (`ChannelGateway._follow`). This is only the
holder: tasks keyed by chat, and cancel-all on shutdown.

A strong reference is mandatory, not bookkeeping: asyncio holds only weak
references to tasks, so an unreferenced task can be collected mid-send.
`hermes-agent` keeps the same collections for the same reason.

In memory, so single-process. Multi-pod needs shared storage and a lease;
`RunStore` is what breaks first, not this. DESIGN.md §7.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

# Telegram chat `123` and Discord channel `123` are different conversations, so
# nothing is keyed on the chat id alone.
ChatKey = tuple[str, str]


class ChatTasks:
    """The running task for each chat, if it has one."""

    def __init__(self) -> None:
        self._tasks: dict[ChatKey, asyncio.Task[None]] = {}

    def start(self, key: ChatKey, work: Coroutine[None, None, None]) -> None:
        """Run `work` as this chat's task.

        Deliberately no "cancel the previous task for this chat". Two cannot
        overlap: a turn only starts when none is active, and the one path that
        starts while another is live is the drain — where the "previous" *is*
        the calling task, so the guard only cancelled itself.
        """
        task = asyncio.create_task(work)
        self._tasks[key] = task
        # Or every chat that has ever had a turn leaves a completed task here
        # until the process stops. Guarded on identity because a newer task
        # may already own the key.
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
