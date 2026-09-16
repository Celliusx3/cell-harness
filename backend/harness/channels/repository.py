"""The storage port for per-chat state, and its failures.

The **interface only**, mirroring `session/repository.py`. `JsonlChatRepository`
is one implementation; SQLite would be another, swapped at the composition root.

What a chat needs remembered is small, and all of it is load-bearing:

- **which conversation it is**, so a text continues yesterday's thread
- **what has already been delivered**, so a restart does not re-send a reply
- **what arrived while busy**, so a message during a turn is answered not dropped

There is deliberately **no record of which messages have been seen** — see
`channels/__init__.py` on why a redelivered message is answered again rather than
guarded against.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ChatStateError(RuntimeError):
    """Chat state could not be read or written."""


class ChatState(BaseModel):
    """Everything remembered about one chat."""

    model_config = ConfigDict(frozen=True)

    # Which platform. Part of the identity, not decoration: Telegram chat `123`
    # and Discord channel `123` are different conversations.
    channel: str
    # A string even where the platform uses an integer, so one shape covers
    # Telegram's signed ints and WhatsApp's phone numbers.
    chat_id: str
    # Empty until this chat's first *message*, not its first contact. Phase 3's
    # `create()` is lazily materialized — it writes nothing — so creating a
    # session for a chat that only ever sent `/stop` would leave an id that
    # `resume()` cannot find and the browser never lists. `/new` clears this.
    conversation_id: str = ""
    # A cursor over the **session log** — the same numbering the browser uses for
    # `?after=N`. Events below this index have been delivered to this chat.
    #
    # Delivering by log position rather than by run is what lets a reply typed in
    # the browser also reach the phone: the channel watches the conversation, not
    # the turn it happened to start.
    delivered_through: int = 0
    # Messages that arrived while a turn was running. Drained as **one** turn
    # when it settles — several lines typed in a burst meant one thing.
    pending: tuple[str, ...] = ()


class ChatRepository(Protocol):
    """Store and reload per-chat state."""

    async def load(self, channel: str, chat_id: str) -> ChatState | None:
        """This chat's state, or `None` if it has never been seen."""
        ...

    async def save(self, state: ChatState) -> None:
        """Durably record one chat's state, replacing what was there."""
        ...

    async def chats_of(self, conversation_id: str) -> list[ChatState]:
        """Every chat currently pointing at this conversation.

        The reverse of `load`, for the one thing that starts a turn without a
        chat in hand: a client tool answered from the browser page. The turn
        it opens must be followed by whichever chats own the conversation, or
        their reply lands only in the log.
        """
        ...

    async def cursor(self, channel: str) -> str:
        """Where this platform's ingress got to, or `""` if it has not started.

        A free-form string because only its own ingress reads it: Telegram keeps
        a `getUpdates` offset here, and a webhook-driven platform keeps nothing.
        """
        ...

    async def set_cursor(self, channel: str, value: str) -> None:
        """Record how far the ingress has got."""
        ...
