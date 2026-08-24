"""The session service — decisions about storage, not storage itself.

`Session` is the in-memory log and knows nothing about being saved. A
`SessionRepository` knows how to save but nothing about when. This joins them.

It holds **no state of its own**. How much of a log is durable is a fact about
storage, so the repository answers it (`stored_count`) and this asks — rather
than keeping a second copy that could drift out of step with the disk.

Layered deliberately, the way cell-bot separates `repository.py` from
`service.py`. Everything below depends on the `SessionRepository` Protocol, so a
SQLite or Postgres backend swaps in at the composition root and this file does
not change.

Writes happen at a checkpoint, not per event. A turn appends hundreds of
`assistant/chunk` events; fsyncing each would make streaming unusable, and
batching by a timer (as dsh does) is machinery we do not need yet. Instead
`flush` is called at the moments durability actually matters:

- **before a model request** — never send a prompt that is not yet on disk, or a
  crash leaves a reply to a question the log cannot show
- **at the end of a turn** — so a completed conversation is durable even if the
  process never runs another turn

That is dsh's `session-checkpoint-policy` reduced to its two load-bearing
moments. Buffering until the checkpoint *is* the batch.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from harness.session.log import Session
from harness.session.models import SessionHeader
from harness.session.repair import repair
from harness.session.repository import SessionRepository


class SessionService:
    """Creates, resumes, and durably records sessions.

    The **service** layer: it owns the decisions — when to write, whether a log
    needs repairing, what a new session's header says. Storage is a
    `SessionRepository` it is handed, so pointing this at SQLite is a change at
    the composition root and nowhere else.
    """

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

    async def create(self) -> Session:
        """A new, empty session. Writes nothing until its first flush."""
        header = SessionHeader(id=self._new_id(), created_at=self._now())
        await self._repository.create(header)
        return Session(header)

    async def read(self, session_id: str) -> Session:
        """Load a stored session **as it is**, repairing nothing.

        The display path, next to `resume`'s write path. Two reasons they differ:

        - A `GET` must not mutate the log. `resume` appends its repair, so serving
          a page view through it would make every page view a write.
        - After a crash the honest thing to show is what happened — an assistant
          message whose tool never answered — not the synthetic result that exists
          to make a *provider* accept the history.

        The repair is not hidden from a UI by this: it lands on the log when the
        next turn starts, and reaches the browser as ordinary events on the
        stream.
        """
        header, events = await self._repository.load(session_id)
        return Session(header, events)

    async def resume(self, session_id: str) -> Session:
        """Load a stored session, repairing whatever a dead process left open.

        Repair is **committed**, not applied in memory only: the synthetic
        closers are appended like any other events, so the next load finds a
        balanced log and `repair` has nothing left to do. That is what makes
        resuming twice safe.
        """
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

    async def list(self) -> list[SessionHeader]:
        """Every stored session, newest first."""
        return await self._repository.list()
