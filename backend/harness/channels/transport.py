"""What a platform must provide, and what arrives from one.

**One object per platform.** A `Channel` is everything Telegram — or the browser,
or WhatsApp — can do: receive until stopped, and say how it wants a lost
conversation handled. `hermes-agent` takes the same shape, one adapter covering a
whole platform; `duta-ilmu` splits sending from receiving, which organises code
neatly but makes a platform two objects to wire when it is really one.

**Sending is a separate Protocol, because not every platform can be sent to.**
See `Pushing`.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

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
