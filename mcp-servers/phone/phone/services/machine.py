"""The one phone: made or started on first use, then waited on until Android has booted."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from phone.clock import Clock
from phone.config import Config
from phone.engine import Engine
from phone.models.command import COMMAND_TIMEOUT_SECONDS
from phone.models.errors import EngineError
from phone.models.phone import PhoneSpec, Program

logger = logging.getLogger("phone")

BOOT_POLL_SECONDS = 2
BOOT_TIMEOUT_SECONDS = 180
BOOT_COMPLETED = Program(argv=("android", "getprop sys.boot_completed"), env={})


def phone_spec(config: Config) -> PhoneSpec:
    return PhoneSpec(name=config.name, image=config.image)


class Machine:
    """One microVM per server process, shared by every bot."""

    def __init__(self, *, engine: Engine, config: Config, clock: Clock) -> None:
        self._engine = engine
        self._config = config
        self._clock = clock
        self._lock = asyncio.Lock()
        self._booted = False

    @asynccontextmanager
    async def in_use(self) -> AsyncIterator[None]:
        """One tool call: the phone is running and Android has booted for its length."""
        await self._ensure_running()
        yield

    async def _ensure_running(self) -> None:
        async with self._lock:
            spec = phone_spec(self._config)
            state = await self._engine.state(spec.name)
            if state == "stopped":
                logger.info("starting the phone %s", spec.name)
                await self._engine.start(spec.name)
                self._booted = False
            elif state == "missing":
                logger.info("making the phone %s", spec.name)
                await self._engine.create(spec)
                self._booted = False
            if not self._booted:
                await self._wait_for_android(spec.name)
                self._booted = True

    async def _wait_for_android(self, name: str) -> None:
        deadline = self._clock.now() + BOOT_TIMEOUT_SECONDS
        while not await self._has_booted(name):
            if self._clock.now() >= deadline:
                raise EngineError(
                    f"Android did not finish booting within {BOOT_TIMEOUT_SECONDS} seconds"
                )
            await self._clock.sleep(BOOT_POLL_SECONDS)

    async def _has_booted(self, name: str) -> bool:
        """Whether Android says it has booted; before it runs, the helper fails, which is a no."""
        completed = await self._engine.run(
            name, BOOT_COMPLETED, stdin=None, timeout_seconds=COMMAND_TIMEOUT_SECONDS
        )
        return completed.stdout.strip() == "1"
