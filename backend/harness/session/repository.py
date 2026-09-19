"""The durable-storage seam: what a session repository must do, and its failures."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from harness.session.models import SessionEvent, SessionHeader


class SessionNotFoundError(RuntimeError):
    """No stored session with that id."""


class SessionFormatUnsupportedError(RuntimeError):
    """The log was written by a format version this build does not understand."""


class SessionCorruptionError(RuntimeError):
    """A committed part of the log is unreadable."""


class SessionRepository(Protocol):
    """Store, reload, and list sessions durably."""

    async def create(self, header: SessionHeader) -> None:
        """Register a new session. MAY write nothing until the first append."""
        ...

    async def append(self, session_id: str, events: Sequence[SessionEvent]) -> None:
        """Durably record a batch, continuing the stored log. Append-only."""
        ...

    async def stored_count(self, session_id: str) -> int:
        """How many events are already durable for this session."""
        ...

    async def load(self, session_id: str) -> tuple[SessionHeader, list[SessionEvent]]:
        """Read a session back. Raises if it does not exist or cannot be read."""
        ...

    async def list(self) -> list[SessionHeader]:
        """Every stored session's metadata, newest first."""
        ...
