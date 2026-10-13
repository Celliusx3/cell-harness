"""The person's live screen and shell: one view token, and a hold that keeps the bots off."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import resources

from computer import gateway
from computer.clock import Clock
from computer.desktop import published_port
from computer.docker import COMMAND_TIMEOUT_SECONDS, Docker, DockerError, stdout_of
from computer.machine import GATEWAY_PORT, Machine
from computer.models import ScreenSession

logger = logging.getLogger("computer")

HOLD_DURATION = timedelta(minutes=15)
TOKEN_BYTES = 24
TERMINAL_PROGRAM = "vendor/rakazo_terminal.py"


class NotHeld(RuntimeError):
    """Nobody holds control any more, so a call only the holder may make did nothing."""


@dataclass(frozen=True)
class Hold:
    token: str
    until: datetime


@dataclass(frozen=True)
class Link:
    """A screen session, and the loopback page that shows it."""

    session: ScreenSession
    url: str


class LiveScreen:
    """The screen as the person sees it: watched by anyone, controlled by one person at a time."""

    def __init__(self, *, docker: Docker, container: str, machine: Machine, clock: Clock) -> None:
        self._docker = docker
        self._container = container
        self._machine = machine
        self._clock = clock
        self._view_token = secrets.token_urlsafe(TOKEN_BYTES)
        self._hold: Hold | None = None
        self._expiry: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    def is_held(self) -> bool:
        return self._hold is not None

    @asynccontextmanager
    async def serving(self) -> AsyncIterator[None]:
        """The server's lifespan: a hold's expiry dies with the server."""
        try:
            yield
        finally:
            self._cancel_expiry()

    async def view(self) -> Link:
        async with self._lock:
            await self._run_script(gateway.view_script(self._view_token), "opening the screen")
        session = ScreenSession(mode="view", held_until=None)
        return Link(session=session, url=await self._url(self._view_token, view_only=True))

    async def take_control(self) -> Link:
        """Control for HOLD_DURATION from now; taking it again while held keeps the token."""
        async with self._lock:
            token = secrets.token_urlsafe(TOKEN_BYTES) if self._hold is None else self._hold.token
            await self._run_script(
                gateway.take_control_script(token), "taking control of the screen"
            )
            hold = Hold(token=token, until=self._clock.wall() + HOLD_DURATION)
            self._hold = hold
            self._machine.pause_idle_stop()
            self._cancel_expiry()
            self._expiry = asyncio.create_task(self._expire(hold))
        session = ScreenSession(mode="control", held_until=hold.until)
        return Link(session=session, url=await self._url(token, view_only=False))

    async def release(self) -> ScreenSession:
        async with self._lock:
            if self._hold is not None:
                await self._run_script(
                    gateway.release_script(self._hold.token), "handing the screen back"
                )
                self._end_hold()
        return ScreenSession(mode="view", held_until=None)

    async def open_terminal(self) -> str:
        """A link to a new shell on the computer, for the person holding control."""
        program = resources.files("computer").joinpath(TERMINAL_PROGRAM).read_text("utf-8")
        token = secrets.token_urlsafe(TOKEN_BYTES)
        async with self._lock:
            if self._hold is None:
                raise NotHeld
            script = gateway.open_terminal_script(self._hold.token, token)
            completed = await self._docker.run(
                ["exec", "-i", self._container, "bash", "-c", script],
                stdin=program,
                timeout_seconds=COMMAND_TIMEOUT_SECONDS,
            )
            stdout_of(completed, "opening the shell")
        return gateway.terminal_url(await self._gateway_host_port(), token)

    async def _expire(self, hold: Hold) -> None:
        await self._clock.sleep(HOLD_DURATION.total_seconds())
        self._expiry = None
        async with self._lock:
            if self._hold is not hold:
                return
            logger.info("the person's hold on the computer %s ran out", self._container)
            try:
                await self._run_script(
                    gateway.release_script(hold.token), "handing the screen back"
                )
            except DockerError as err:
                logger.error("the control screen of %s may still be open: %s", self._container, err)
            self._end_hold()

    def _end_hold(self) -> None:
        self._cancel_expiry()
        self._hold = None
        self._machine.resume_idle_stop()

    def _cancel_expiry(self) -> None:
        if self._expiry is not None:
            self._expiry.cancel()
            self._expiry = None

    async def _url(self, token: str, *, view_only: bool) -> str:
        return gateway.screen_url(await self._gateway_host_port(), token, view_only=view_only)

    async def _gateway_host_port(self) -> int:
        published = await self._output(["port", self._container, str(GATEWAY_PORT)], "docker port")
        return published_port(published, GATEWAY_PORT)

    async def _run_script(self, script: str, action: str) -> None:
        await self._output(["exec", self._container, "bash", "-c", script], action)

    async def _output(self, args: Sequence[str], action: str) -> str:
        completed = await self._docker.run(args, stdin="", timeout_seconds=COMMAND_TIMEOUT_SECONDS)
        return stdout_of(completed, action)
