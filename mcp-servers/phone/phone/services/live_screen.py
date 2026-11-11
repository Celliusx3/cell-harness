"""The person's live screen: one view token, and a hold that keeps the bots off."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

from phone.clock import Clock
from phone.engine import Engine
from phone.models.command import stdout_of
from phone.models.errors import EngineError
from phone.models.phone import LOOPBACK, Program
from phone.models.screen import ScreenMode, ScreenSession
from phone.services.machine import GATEWAY_PORT, Machine

logger = logging.getLogger("phone")

HOLD_DURATION = timedelta(minutes=15)
TOKEN_BYTES = 24
SCREEN_PROGRAM = "phone-screen"
SESSION_TIMEOUT_SECONDS = 120.0
RELEASE = Program(argv=(SCREEN_PROGRAM, "release"), env={})


@dataclass(frozen=True)
class Hold:
    token: str
    until: datetime


@dataclass(frozen=True)
class Link:
    """A screen session, and the loopback page that shows it."""

    session: ScreenSession
    url: str


def screen_url(port: int, token: str, *, view_only: bool) -> str:
    """noVNC's page on the published gateway port, opening the screen this token names."""
    query = urlencode({"path": f"websockify?token={token}", "view_only": "1" if view_only else "0"})
    return f"http://{LOOPBACK}:{port}/embed.html?{query}"


def session_program(mode: ScreenMode, token: str) -> Program:
    return Program(argv=(SCREEN_PROGRAM, mode, token), env={})


class LiveScreen:
    """The phone as the person sees it: watched by anyone, controlled by one person at a time."""

    def __init__(self, *, engine: Engine, name: str, machine: Machine, clock: Clock) -> None:
        self._engine = engine
        self._name = name
        self._machine = machine
        self._clock = clock
        self._view_token = secrets.token_urlsafe(TOKEN_BYTES)
        self._hold: Hold | None = None
        self._expiry: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
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
        """The phone to watch; while the person holds it, their hold, for the page to hand back."""
        if self._hold is not None:
            hold = self._hold
            session = ScreenSession(mode="control", held_until=hold.until)
            return Link(session=session, url=await self._url(hold.token, view_only=False))
        async with self._lock:
            await self._run(session_program("view", self._view_token), "opening the screen")
        session = ScreenSession(mode="view", held_until=None)
        return Link(session=session, url=await self._url(self._view_token, view_only=True))

    async def take_control(self) -> Link:
        """Control for HOLD_DURATION from now; taking it again while held keeps the token."""
        async with self._lock:
            token = secrets.token_urlsafe(TOKEN_BYTES) if self._hold is None else self._hold.token
            await self._run(session_program("control", token), "taking control of the phone")
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
                await self._run(RELEASE, "handing the phone back")
                self._end_hold()
        return ScreenSession(mode="view", held_until=None)

    async def _expire(self, hold: Hold) -> None:
        await self._clock.sleep(HOLD_DURATION.total_seconds())
        self._expiry = None
        async with self._lock:
            if self._hold is not hold:
                return
            logger.info("the person's hold on the phone %s ran out", self._name)
            try:
                await self._run(RELEASE, "handing the phone back")
            except EngineError as err:
                logger.error("the control screen of %s may still be open: %s", self._name, err)
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
        port = await self._engine.host_port(self._name, GATEWAY_PORT)
        return screen_url(port, token, view_only=view_only)

    async def _run(self, program: Program, action: str) -> None:
        completed = await self._engine.run(
            self._name, program, stdin=None, timeout_seconds=SESSION_TIMEOUT_SECONDS
        )
        stdout_of(completed, action, error=EngineError)
