"""What a platform must provide, and what arrives from one."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from harness.tools.client import PendingCall

logger = logging.getLogger("harness.channels")

OnMissing = Literal["recreate", "raise"]


class InboundMessage(BaseModel):
    """One message arriving from any platform, normalized."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    channel: str
    chat_id: str
    text: str


class DuplicateChannelError(RuntimeError):
    """Two channels registered under one platform name."""


class UnknownChannelError(RuntimeError):
    """A message arrived from a platform with no registered transport."""


class Channel(Protocol):
    """One whole platform: receiving, and how it recovers."""

    @property
    def channel(self) -> str:
        """The platform's name, as it appears in stored state and logs."""
        ...

    @property
    def on_missing(self) -> OnMissing:
        """What the gateway should do when this chat's conversation is gone."""
        ...

    async def run(self) -> None:
        """Receive until cancelled, handing each message to the gateway."""
        ...


@runtime_checkable
class Pushing(Protocol):
    """A platform the gateway can send a reply *to*."""

    async def send_message(self, chat_id: str, text: str) -> None:
        """Deliver `text`."""
        ...

    async def send_typing(self, chat_id: str) -> None:
        """Show that a reply is coming, if the platform has the idea."""
        ...

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        """Deliver `text` with `url` to open — how an MCP App reaches a chat."""
        ...

    async def ask_client(self, chat_id: str, request: PendingCall, url: str) -> None:
        """Ask the person for what a client tool wants."""
        ...


class RunningChannel:
    """A channel and the task listening on it, under one platform name."""

    def __init__(self, channel: Channel) -> None:
        self.channel = channel
        self._task: asyncio.Task[None] | None = None

    @property
    def name(self) -> str:
        return self.channel.channel

    async def start(self) -> None:
        logger.info("%s channel starting", self.name)
        self._task = asyncio.create_task(self.channel.run())
        self._task.add_done_callback(self._report_exit)

    async def aclose(self) -> None:
        """Stop receiving."""
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def _report_exit(self, task: asyncio.Task[None]) -> None:
        """Say something when receiving ends on its own."""
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("%s channel stopped: %s", self.name, error, exc_info=error)
        elif isinstance(self.channel, Pushing):
            logger.warning("%s channel stopped; it will not answer", self.name)
        else:
            logger.info("%s channel stopped waiting", self.name)
