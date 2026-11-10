"""A count of writes to the bots file, and a way to wait for the next one."""

from __future__ import annotations

import asyncio


class BotListChanges:
    """How many times the bots file has been written since start, and who waits for the next."""

    def __init__(self) -> None:
        self.version = 0
        self._written = asyncio.Event()

    def bump(self) -> None:
        """Count one write, and release everyone waiting in `after`."""
        self.version += 1
        self._written.set()
        self._written = asyncio.Event()

    async def after(self, version: int) -> int:
        """The version once it is no longer `version`."""
        while self.version == version:
            await self._written.wait()
        return self.version
