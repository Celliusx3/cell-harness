"""The one computer: made, started, adopted at startup, and stopped when nobody uses it."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from computer.clock import Clock
from computer.command import COMMAND_TIMEOUT_SECONDS, EngineError, stdout_of
from computer.config import Config
from computer.engine import Engine, HomeVolume, PcSpec, Program, SharedFolder
from computer.jobs import RUNNING_JOBS_SCRIPT

logger = logging.getLogger("computer")

HOME = "/home/rakazo"
JOBS_ROOT = f"{HOME}/.shell"
DISPLAY = ":1"
API_PORT = 7070
GATEWAY_PORT = 6080
API_TOKEN_VARIABLE = "RAKAZO_COMPUTER_CONTROL_TOKEN"
SHM_MEGABYTES = 256
OPEN_CHROME = Program(argv=("rakazo-focus-or-launch", "rakazo-browser"), env={})


def shared_folders(config: Config) -> tuple[SharedFolder, ...]:
    """The chat files read-write and every skill folder read-only, each at its own path."""
    return (
        SharedFolder(path=config.files_dir, writable=True),
        *(SharedFolder(path=folder, writable=False) for folder in config.skills_dirs),
    )


def pc_spec(config: Config, api_token: str, host_service_ports: tuple[int, ...]) -> PcSpec:
    """The PC as Rakazo creates its computer, with its API and gateway published."""
    name = config.container_name
    return PcSpec(
        name=name,
        image=config.image,
        env={"DISPLAY": DISPLAY, "HOME": HOME, API_TOKEN_VARIABLE: api_token},
        home=HomeVolume(name=f"{name}-home", guest_path=HOME),
        shared_folders=shared_folders(config),
        published_ports=(API_PORT, GATEWAY_PORT),
        host_service_ports=host_service_ports,
        shm_megabytes=SHM_MEGABYTES,
    )


class Machine:
    """One container per server process, shared by every bot."""

    def __init__(
        self,
        *,
        engine: Engine,
        config: Config,
        clock: Clock,
        host_service_ports: tuple[int, ...],
    ) -> None:
        self._engine = engine
        self._config = config
        self._clock = clock
        self._host_service_ports = host_service_ports
        self._lock = asyncio.Lock()
        self._idle: asyncio.Task[None] | None = None
        self._idle_stop_paused = False
        self._shape_checked = False

    @asynccontextmanager
    async def serving(self) -> AsyncIterator[None]:
        """The server's lifespan: adopt a running computer, and leave it running on the way out."""
        await self._adopt()
        try:
            yield
        finally:
            self._cancel_idle_stop()

    @asynccontextmanager
    async def in_use(self) -> AsyncIterator[None]:
        """One tool call: the computer runs for its length, and the idle stop restarts after."""
        self._cancel_idle_stop()
        try:
            await self._ensure_running()
            yield
        finally:
            self._restart_idle_stop()

    def pause_idle_stop(self) -> None:
        """The person has the screen: the idle stop waits until they hand it back."""
        self._idle_stop_paused = True
        self._cancel_idle_stop()

    def resume_idle_stop(self) -> None:
        self._idle_stop_paused = False
        self._restart_idle_stop()

    async def _adopt(self) -> None:
        name = self._config.container_name
        try:
            state = await self._engine.state(name)
        except EngineError as err:
            logger.warning("cannot see the computer %s at startup: %s", name, err)
            return
        if state == "running":
            logger.info("adopting the running computer %s", name)
            await self._open_chrome()
            self._restart_idle_stop()

    async def _ensure_running(self) -> None:
        async with self._lock:
            spec = pc_spec(self._config, secrets.token_hex(16), self._host_service_ports)
            state = await self._engine.state(spec.name)
            if state != "missing" and not self._shape_checked:
                reason = await self._engine.replacement_reason(spec)
                if reason is not None:
                    logger.info("replacing the computer %s: %s", spec.name, reason)
                    await self._engine.remove(spec.name)
                    state = "missing"
            self._shape_checked = True
            if state == "running":
                return
            if state == "stopped":
                await self._engine.start(spec.name)
            else:
                await self._engine.create(spec)
            await self._open_chrome()

    async def _open_chrome(self) -> None:
        name = self._config.container_name
        try:
            stdout_of(await self._engine.launch(name, OPEN_CHROME), "opening Chrome")
        except EngineError as err:
            logger.warning("Chrome did not open on the computer %s: %s", name, err)

    def _restart_idle_stop(self) -> None:
        self._cancel_idle_stop()
        if not self._idle_stop_paused:
            self._idle = asyncio.create_task(self._stop_when_idle())

    def _cancel_idle_stop(self) -> None:
        if self._idle is not None:
            self._idle.cancel()
            self._idle = None

    async def _stop_when_idle(self) -> None:
        await self._clock.sleep(self._config.idle_minutes * 60)
        self._idle = None
        async with self._lock:
            name, minutes = self._config.container_name, self._config.idle_minutes
            if await self._is_running_a_command():
                logger.info("the computer %s stays on: a command is still running in it", name)
                self._restart_idle_stop()
                return
            logger.info("stopping the computer %s after %d idle minutes", name, minutes)
            try:
                await self._engine.stop(name)
            except EngineError as err:
                logger.warning("idle stop of the computer %s did not happen: %s", name, err)

    async def _is_running_a_command(self) -> bool:
        """Whether a bot's command still runs in the computer; True when that cannot be told."""
        name = self._config.container_name
        look = Program(argv=("python3", "-c", RUNNING_JOBS_SCRIPT, JOBS_ROOT), env={})
        try:
            completed = await self._engine.run(
                name, look, stdin=None, timeout_seconds=COMMAND_TIMEOUT_SECONDS
            )
            return bool(stdout_of(completed, "looking for running commands").split())
        except EngineError as err:
            logger.warning("the computer %s stays on: %s", name, err)
            return True
