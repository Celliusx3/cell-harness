"""What a platform must provide, and what arrives from one.

**One object per platform.** A `Channel` is everything Telegram — or the browser,
or WhatsApp — can do: receive until stopped, and say how it wants a lost
conversation handled. `hermes-agent` takes the same shape, one adapter covering a
whole platform; `duta-ilmu` splits sending from receiving, which organises code
neatly but makes a platform two objects to wire when it is really one.

**Sending is a separate Protocol, because not every platform can be sent to.**
See `Pushing`.

`RunningChannel` is the one concrete class here: a `Channel` and the task
running its `run()`, held together so the gateway has one thing per platform to
start, reply through, and stop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("harness.channels")

# What to do when a chat's conversation id names nothing on disk. A messenger must
# `recreate` — the chat is otherwise permanently broken and the person holding the
# phone cannot fix it. An API must `raise`, because inventing a conversation for a
# mistyped id is a worse answer than a 404.
OnMissing = Literal["recreate", "raise"]


class InboundMessage(BaseModel):
    """One message arriving from any platform, normalized.

    Three fields, and no message id: the only thing the shared path would have done
    with one is recognise a repeat, and this phase deliberately does not — see
    `channels/__init__.py`.
    """

    # `extra="forbid"` because the alternative is silence. Pydantic ignores unknown
    # fields by default, and when `message_id` was removed a test kept passing it
    # and kept passing — the field simply vanished.
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Two jobs: part of a chat's identity, so Telegram chat `123` and Discord
    # channel `123` stay separate; and how the gateway finds the channel to reply
    # through.
    channel: str
    # A string even where the platform uses an integer, so one shape covers
    # Telegram's signed ints, WhatsApp's phone numbers and a browser's session id.
    chat_id: str
    text: str


class DuplicateChannelError(RuntimeError):
    """Two channels registered under one platform name."""


class UnknownChannelError(RuntimeError):
    """A message arrived from a platform with no registered transport.

    Loud rather than ignored: it means a channel was wired to receive but not to
    reply, and a bot that reads everything and answers nothing looks like a hang.
    """


class Channel(Protocol):
    """One whole platform: receiving, and how it recovers.

    An implementation owns its own limits. Telegram's 4096-character cap and its
    refusal to render unescaped MarkdownV2 are `TelegramChannel`'s problem, not the
    gateway's.
    """

    @property
    def channel(self) -> str:
        """The platform's name, as it appears in stored state and logs."""
        ...

    @property
    def on_missing(self) -> OnMissing:
        """What the gateway should do when this chat's conversation is gone."""
        ...

    async def run(self) -> None:
        """Receive until cancelled, handing each message to the gateway.

        The part that genuinely differs — Telegram long-polls, WhatsApp serves a
        webhook, Discord holds a websocket. A channel whose receiving is driven by
        something else entirely, as `WebChannel`'s is by uvicorn, waits here
        instead; that is not a stub, it really does receive until cancelled.
        """
        ...


@runtime_checkable
class Pushing(Protocol):
    """A platform the gateway can send a reply *to*.

    Separate from `Channel` because a browser has no address. `bot.send_message` is
    an outgoing call to somewhere; a browser is not somewhere, it comes and reads
    the session log itself. Every possible body for a browser `send_message` is
    wrong — `pass` loses replies silently, `raise` is a landmine, and returning a
    failure is what `hermes-agent` does:

        # gateway/platforms/api_server.py:4174
        return SendResult(success=False, error="API server uses ... not send()")

    Four of their modules then special-case that platform back out. So the method
    is absent here rather than present and broken, and the gateway asks
    `isinstance(channel, Pushing)` before it ever tries.
    """

    async def send_message(self, chat_id: str, text: str) -> None:
        """Deliver `text`. Raises if it could not be delivered.

        Takes a whole reply and is responsible for it arriving, splitting it if the
        platform has a length limit.
        """
        ...

    async def send_typing(self, chat_id: str) -> None:
        """Show that a reply is coming, if the platform has the idea.

        Best-effort by contract: a platform without typing indicators — email, SMS
        — implements this as a no-op, and no caller should treat a failure here as
        a reason not to send the actual reply.
        """
        ...

    async def send_link(self, chat_id: str, text: str, url: str) -> None:
        """Deliver `text` with `url` to open — how an MCP App reaches a chat.

        A chat cannot render HTML, so an app is a page the harness serves and
        the chat gets a way to it: a button that opens it where the platform
        has buttons (Telegram, Discord), the URL as text where it does not.
        Raises if it could not be delivered, like `send_message`.
        """
        ...


class RunningChannel:
    """A channel, and the task listening on it — useless apart, and looked up
    by the same platform name."""

    def __init__(self, channel: Channel) -> None:
        # Public, because the gateway replies through the same object it
        # supervises.
        self.channel = channel
        self._task: asyncio.Task[None] | None = None

    @property
    def name(self) -> str:
        return self.channel.channel

    async def start(self) -> None:
        logger.info("%s channel starting", self.name)
        self._task = asyncio.create_task(self.channel.run())
        # Without this a dead channel is *silent*: `create_task` holds the
        # exception until someone awaits the task, and nothing does until
        # shutdown. That is how a dead poller once looked like a working one.
        self._task.add_done_callback(self._report_exit)

    async def aclose(self) -> None:
        """Stop receiving. Delivery is shared, so the gateway closes that once
        after every channel is down — here would close it on the first."""
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
            # A pull channel's `run()` returning means only that it stopped
            # waiting — its receiving is somewhere else entirely (uvicorn serves
            # `WebChannel`'s routes), so it goes on answering. Saying "it will not
            # answer" here would be the false alarm that teaches people to ignore
            # the true one.
            logger.info("%s channel stopped waiting", self.name)
