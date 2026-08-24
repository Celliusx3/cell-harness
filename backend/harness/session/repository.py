"""The durable-storage seam: what a session repository must do, and its failures.

The **interface only**. `JsonlSessionRepository` is one implementation; a SQLite
or Postgres one satisfies the same four methods and swaps in at the composition
root with nothing else changing. `SessionService` depends on this Protocol, never
on a concrete backend, which is the whole point of the split.

The persisted unit **is** the `SessionEvent`. There is no parallel "stored
message" type, because the log is the source of truth and a second shape would be
a second thing to keep in step. Metadata that is not a conversation fact travels
as the `SessionHeader` (see `header.py`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from harness.session.models import SessionEvent, SessionHeader


class SessionNotFoundError(RuntimeError):
    """No stored session with that id."""


class SessionFormatUnsupportedError(RuntimeError):
    """The log was written by a format version this build does not understand.

    Refuses rather than guessing. Migration is a real feature; best-effort
    parsing of a format we do not know is how a log becomes quietly unreadable.
    """


class SessionCorruptionError(RuntimeError):
    """A committed part of the log is unreadable.

    Distinct from a torn tail — see `load`. Skipping a bad line in the middle
    would hand the model a history with a hole in it and no way to know.
    """


class SessionRepository(Protocol):
    """Store, reload, and list sessions durably."""

    async def create(self, header: SessionHeader) -> None:
        """Register a new session. MAY write nothing until the first append."""
        ...

    async def append(self, session_id: str, events: Sequence[SessionEvent]) -> None:
        """Durably record a batch, continuing the stored log. Append-only."""
        ...

    async def stored_count(self, session_id: str) -> int:
        """How many events are already durable for this session.

        The **one** cursor. A caller works out what to append by asking, rather
        than remembering — so there is no second copy of this number to drift out
        of step with the store. Zero for a session with nothing written yet,
        including one that was created and never appended to.
        """
        ...

    async def load(self, session_id: str) -> tuple[SessionHeader, list[SessionEvent]]:
        """Read a session back. Raises if it does not exist or cannot be read."""
        ...

    async def list(self) -> list[SessionHeader]:
        """Every stored session's metadata, newest first."""
        ...
