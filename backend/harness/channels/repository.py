"""The storage port for per-chat state, and its failures."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ChatStateError(RuntimeError):
    """Chat state could not be read or written."""


class ChatState(BaseModel):
    """Everything remembered about one chat."""

    model_config = ConfigDict(frozen=True)

    channel: str
    chat_id: str
    conversation_id: str = ""
    delivered_through: int = 0
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
        """Every chat currently pointing at this conversation."""
        ...

    async def cursor(self, channel: str) -> str:
        """Where this platform's ingress got to, or `""` if it has not started."""
        ...

    async def set_cursor(self, channel: str, value: str) -> None:
        """Record how far the ingress has got."""
        ...
