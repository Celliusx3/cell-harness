"""What a platform must provide, and what arrives from one.

**One object per platform.** `Channel` is everything Telegram — or WhatsApp, or
Discord — can do: receive until stopped, send a reply, show that a reply is
coming. `hermes-agent` takes the same shape, with one `BasePlatformAdapter`
covering connect, receive and send; `duta-ilmu` splits sending from receiving
into separate modules, which is a fine way to organise *code* but makes a
platform two objects to wire when it is really one.

**One Protocol.** There were briefly two — a narrow `ChatTransport` for sending
and a `Channel` extending it — on the argument that the gateway only ever sends.
That stopped being true when the gateway took on supervising the channels it
sends through: it needs `run()`, it holds one registry, and the narrow half was
left as a name with no user. An interface that only documents is a comment with
extra steps.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class InboundMessage(BaseModel):
    """One message arriving from any platform, normalized.

    Three fields, and no message id: the only thing the shared path would have
    done with one is recognise a repeat, and this phase deliberately does not —
    see `channels/__init__.py`. A platform id comes back the moment something
    downstream has a reason to read it.
    """

    # `extra="forbid"` because the alternative is silence. Pydantic ignores
    # unknown fields by default, and when `message_id` was removed a test kept
    # passing it and kept passing — the field simply vanished. A platform that
    # sends something this does not model should hear about it.
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Which platform this arrived on. Two jobs: it is part of a chat's identity,
    # so Telegram chat `123` and Discord channel `123` stay separate; and it is
    # how the gateway finds the transport to reply through.
    channel: str
    # A string even where the platform uses an integer, so one shape covers
    # Telegram's signed ints, WhatsApp's phone numbers and Slack's `C0…` ids.
    chat_id: str
    text: str


class Channel(Protocol):
    """One whole platform: receiving, sending, and showing that a reply is coming.

    An implementation owns its own limits. Telegram's 4096-character cap and its
    refusal to render unescaped MarkdownV2 are `TelegramChannel`'s problem, not
    the gateway's: `send_message` takes a whole reply and is responsible for it
    arriving, splitting if it must.
    """

    @property
    def channel(self) -> str:
        """The platform's name, as it appears in stored state and logs."""
        ...

    async def send_message(self, chat_id: str, text: str) -> None:
        """Deliver `text`. Raises if it could not be delivered."""
        ...

    async def send_typing(self, chat_id: str) -> None:
        """Show that a reply is coming, if the platform has the idea.

        Best-effort by contract: a platform without typing indicators — email,
        SMS — implements this as a no-op, and no caller should treat a failure
        here as a reason not to send the actual reply.
        """
        ...

    async def run(self) -> None:
        """Receive until cancelled, handing each message to the gateway.

        The part that genuinely differs — Telegram long-polls, WhatsApp serves a
        webhook, Discord holds a websocket — and all the gateway asks is that it
        keeps going until cancelled.
        """
        ...
