"""The one phone: made or started on first use, waited on until Android boots, stopped when idle."""

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
        self._idle: asyncio.Task[None] | None = None

    @asynccontextmanager
    async def serving(self) -> AsyncIterator[None]:
        """The server's lifespan: the phone is left running on the way out, its idle stop not."""
        try:
            yield
        finally:
            self._cancel_idle_stop()

    @asynccontextmanager
    async def in_use(self) -> AsyncIterator[None]:
        """One tool call: the booted phone for its length, and the idle stop restarts after."""
        self._cancel_idle_stop()
        try:
            await self._ensure_running()
            yield
        finally:
            self._restart_idle_stop()

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

    def _restart_idle_stop(self) -> None:
        self._cancel_idle_stop()
        self._idle = asyncio.create_task(self._stop_when_idle())

    def _cancel_idle_stop(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
            self._idle = None

    async def _stop_when_idle(self) -> None:
        await self._clock.sleep(self._config.idle_minutes * 60)
        self._idle = None
        async with self._lock:
            name, minutes = self._config.name, self._config.idle_minutes
            logger.info("stopping the phone %s after %d idle minutes", name, minutes)
            self._booted = False
            try:
                await self._engine.stop(name)
            except EngineError as err:
                logger.warning("idle stop of the phone %s did not happen: %s", name, err)
