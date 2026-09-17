"""`Run` and `RunStore` — driving a turn on a task nobody's connection owns.

One run per conversation at a time. The store starts it, stops it, and answers
"is this conversation busy?"; everything else a client wants comes from the
session log the run is writing into.

**No status vocabulary.** A run is `running` or `settled`, and that is the only
thing anything here needs to know. *Why* a turn ended is already the `reason` on
the log's `turn/end` — so a consumer reads it from the events it is already being
handed, and there is no second copy to disagree with the log. Phase 3 learned this
the expensive way with a duplicated durability cursor.

**No run ids either.** A client subscribes by conversation and stops by
conversation, so nothing ever addressed a run directly.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing

from harness.agent.loop import LoopAgent
from harness.session.log import Session
from harness.session.service import SessionService
from harness.tools.definition import Failure, Ok

logger = logging.getLogger("harness.runs")


class RunAlreadyActive(RuntimeError):
    """This conversation is already running a turn.

    Refused rather than queued. "Still working" is honest; silently ordering
    someone's turns behind each other is a UI that lies about what it did with
    their message.
    """


class Run:
    """One turn in flight, and the log it is writing into.

    Subscribers read `session.events()[cursor:]` directly — see
    `runs/subscribe.py`. There is deliberately no buffer here for them to read
    instead.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.settled = False
        # Guards `settled` **and** the log's growth, together. Two locks, or a
        # lock plus an unsynchronized flag, and a subscriber can read "no new
        # events" then "still running" about two different moments — parking
        # forever on a run that finished in between.
        self.condition = asyncio.Condition()
        # Two tasks: `_inner` runs the turn, `_outer` owns its ending. `stop()`
        # cancels `_inner` only.
        #
        # Measured, because the obvious worry turns out to be unfounded: it is
        # tempting to say the split is required, on the grounds that cancelling
        # `_outer` would skip the flush it owns. It would not. Cancellation
        # propagates through `await _inner`, and `Task.cancel()` delivers
        # `CancelledError` once — a coroutine that catches it keeps running,
        # awaits in its `finally` included. Swapping the target passes every test
        # in `test_runs_stop.py`, which is how the false reasoning was caught.
        #
        # The split is kept for a narrower reason: `_outer` is then never a
        # cancellation target at all, so settling cannot be interrupted by a
        # *second* cancel arriving while it flushes (`stop` racing `aclose`).
        # "Cancel the work, keep the bookkeeping" is also simply what it says.
        self._inner: asyncio.Task[None] | None = None
        self._outer: asyncio.Task[None] | None = None

    @property
    def conversation_id(self) -> str:
        """A conversation *is* a session; this is its id, not a second identity."""
        return self.session.id


class RunStore:
    """Starts and stops turns, and knows which conversations are busy."""

    def __init__(self, service: SessionService, agent: LoopAgent) -> None:
        self._service = service
        self._agent = agent
        self._runs: dict[str, Run] = {}

    def active(self, conversation_id: str) -> Run | None:
        """The run in flight for this conversation, if any."""
        return self._runs.get(conversation_id)

    @property
    def compaction(self):  # -> CompactionService | None; typed loosely to avoid the import
        """The agent's compaction service, for a route deciding whether a manual
        compaction can run before it starts one."""
        return self._agent.compaction

    def start(self, session: Session, prompt: str) -> Run:
        """Begin a turn on a task this store owns.

        **Synchronous, and that is the point.** Two requests arriving together
        would otherwise both pass the check below, both `await` a session load,
        and both start a turn on the same conversation. With the check and the
        registration both synchronous they are atomic on a single-threaded event
        loop, so the second caller gets `RunAlreadyActive` instead of a second
        turn interleaving into one log.
        """
        if session.id in self._runs:
            raise RunAlreadyActive(session.id)
        run = Run(session)
        self._runs[session.id] = run
        # Both tasks created here rather than inside `_drive`, so `stop()` can
        # never arrive before `_inner` exists.
        run._inner = asyncio.create_task(
            self._stream(run, self._agent.run(prompt, session=session))
        )
        run._outer = asyncio.create_task(self._drive(run))
        return run

    def resume(self, session: Session, call_id: str, outcome: Ok | Failure) -> Run:
        """Begin the turn that answers a client tool — the person's answer as
        its first event. Same atomicity as `start`, for the same reason: two
        answers arriving together must not both open a turn."""
        if session.id in self._runs:
            raise RunAlreadyActive(session.id)
        run = Run(session)
        self._runs[session.id] = run
        run._inner = asyncio.create_task(
            self._stream(run, self._agent.resume(call_id, outcome, session=session))
        )
        run._outer = asyncio.create_task(self._drive(run))
        return run

    def compact(self, session: Session) -> Run:
        """Begin a manual compaction as its own run — no model turn, just the
        compaction events. Same atomicity as `start`: the busy check and the
        stream that wakes subscribers come with being a run, so the browser and
        every chat see the summary land the way they see a reply."""
        if session.id in self._runs:
            raise RunAlreadyActive(session.id)
        run = Run(session)
        self._runs[session.id] = run
        run._inner = asyncio.create_task(self._stream(run, self._agent.compact(session=session)))
        run._outer = asyncio.create_task(self._drive(run))
        return run

    async def stop(self, conversation_id: str) -> bool:
        """End a turn early. @returns whether there was one to end.

        Cancelling `_inner` unwinds the loop's generator, whose `finally` writes a
        result for every dispatched tool call and closes the turn `cancelled` —
        without which the next request would be rejected outright for an
        unanswered call.
        """
        run = self._runs.get(conversation_id)
        if run is None or run._inner is None:
            return False
        run._inner.cancel()
        # Awaiting the *outer* task: it is what flushes and settles, so a caller
        # that gets a reply from `stop` knows the cancellation is already durable.
        if run._outer is not None:
            await asyncio.shield(run._outer)
        return True

    async def aclose(self) -> None:
        """Stop every run, for a server shutting down.

        Goes through `stop`, which *awaits* settling — so shutdown does not
        return until every interrupted turn is on disk and resumable.
        """
        for conversation_id in list(self._runs):
            await self.stop(conversation_id)

    async def _stream(self, run: Run, turn: AsyncIterator[object]) -> None:
        """Drive the turn, waking subscribers as the log grows.

        It ignores what the loop yields. The loop appends to the log *before* it
        yields, so by the time this frame runs there is nothing to copy — only to
        announce. That is the whole reason there is no event buffer.
        """
        async with aclosing(turn) as events:
            async for _ in events:
                await self._wake(run)

    async def _drive(self, run: Run) -> None:
        """Own the turn's ending. This task is never cancelled — see `stop`."""
        assert run._inner is not None  # created synchronously in `start`
        try:
            await run._inner
        except asyncio.CancelledError:
            # `stop()` cancelled the inner task. An ordinary ending, not an
            # error: the loop's `finally` has already closed the turn.
            pass
        except Exception:
            # A bug in the loop must still leave a durable, settled run — a
            # conversation stuck at "running" forever cannot even be retried.
            logger.exception("run for conversation %s raised", run.conversation_id)
        finally:
            await self._settle(run)

    async def _settle(self, run: Run) -> None:
        """Make the turn durable, then release everyone waiting on it.

        **Flush first.** A subscriber that sees `settled` stops reading and its
        client may immediately re-fetch the conversation from disk; if the flush
        had not happened, that read would come back short.
        """
        with contextlib.suppress(Exception):
            # A failed flush must not strand the run at `running`. It is logged
            # by the repository and the log stays resumable from its last
            # checkpoint.
            await self._service.flush(run.session)
        async with run.condition:
            run.settled = True
            run.condition.notify_all()
        # Deregistered on settling, with no lingering-run cache: the final flush
        # above means disk now holds everything, so a client reconnecting a moment
        # later gets the same events from the snapshot instead.
        if self._runs.get(run.conversation_id) is run:
            del self._runs[run.conversation_id]

    async def _wake(self, run: Run) -> None:
        async with run.condition:
            run.condition.notify_all()
