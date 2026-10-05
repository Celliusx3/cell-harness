"""The session service — decisions about storage, not storage itself."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from harness.session.log import Session
from harness.session.models import ChatCleared, SessionHeader
from harness.session.repair import repair
from harness.session.repository import SessionRepository


class SessionService:
    """Creates, resumes, and durably records sessions."""

    def __init__(
        self,
        repository: SessionRepository,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        new_id: Callable[[], str] = lambda: str(uuid4()),
    ) -> None:
        self._repository = repository
        self._now = now
        self._new_id = new_id

    async def create(self, session_id: str | None = None) -> Session:
        """A new, empty session, under `session_id` if given. Writes nothing until flushed."""
        header = SessionHeader(
            id=session_id if session_id is not None else self._new_id(), created_at=self._now()
        )
        await self._repository.create(header)
        return Session(header)

    async def read(self, session_id: str) -> Session:
        """Load a stored session **as it is**, repairing nothing."""
        header, events = await self._repository.load(session_id)
        return Session(header, events)

    async def resume(self, session_id: str) -> Session:
        """Load a stored session, repairing whatever a dead process left open."""
        header, events = await self._repository.load(session_id)
        additions = repair(events)
        if additions:
            await self._repository.append(session_id, additions)
            events = [*events, *additions]
        return Session(header, events)

    async def flush(self, session: Session) -> None:
        """Durably record everything appended since the last flush."""
        events = session.events()
        cursor = await self._repository.stored_count(session.id)
        if len(events) == cursor:
            return
        await self._repository.append(session.id, events[cursor:])

    async def clear(self, session_id: str) -> None:
        """Wipe a stored chat: same id, numbering carried on, one `chat/cleared` line."""
        header, events = await self._repository.load(session_id)
        wiped = header.model_copy(update={"numbered_from": header.numbered_from + len(events)})
        await self._repository.restart(wiped, [ChatCleared()])

    async def delete(self, session_id: str) -> None:
        """Remove a stored chat for good; one never written is already gone."""
        await self._repository.delete(session_id)
