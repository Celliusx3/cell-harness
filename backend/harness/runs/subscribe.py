"""Reading a run's log from a cursor, live.

cell-bot's `LocalRunStore.subscribe(run_id, after)`, with one substitution: it
reads the session log rather than a per-run event buffer. Their comment on the
buffer — *"the index into this list **is** the subscriber's cursor"* — is the idea
being reused; the log already had that property, so the buffer was the part that
could go.

The cursor is a **session sequence number** — the log's own index. That is what
makes one number mean the same thing to a disk snapshot and to this stream: a
client that fetched events `0..n` asks here for `after=n` and cannot miss or
repeat one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from harness.runs.store import Run
from harness.session.models import SessionEvent


async def subscribe(run: Run, *, after: int) -> AsyncIterator[SessionEvent]:
    """Every event past `after`, then each new one, until the turn ends.

    Yields **outside** the lock. Holding it across a yield would let a slow
    consumer — a browser on a bad connection — block the run from appending.
    """
    cursor = after
    while True:
        async with run.condition:
            # One wait on one predicate over both facts. Checking them in
            # sequence is the bug this shape exists to prevent: a run that
            # settles between "any new events?" and "still running?" leaves the
            # subscriber waiting for a notify that will never come again.
            # `at=cursor` binds this iteration's cursor rather than closing over
            # the loop variable, so the predicate cannot be affected by the
            # reassignment below even if a future edit defers when it runs.
            await run.condition.wait_for(
                lambda at=cursor: len(run.session.events()) > at or run.settled
            )
            events = list(run.session.events()[cursor:])
            settled = run.settled

        for event in events:
            yield event
        cursor += len(events)

        # Settled is not by itself the end: the events appended by the loop's
        # `finally` — a partial reply, results for abandoned calls, `turn/end` —
        # all land before `settled` is set, so returning on the flag alone drops
        # precisely the record of how the turn ended. Reading the length outside
        # the lock is safe *because* it is settled: a settled run appends nothing.
        if settled and cursor >= len(run.session.events()):
            return
