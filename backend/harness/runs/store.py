"""`Run` and `RunStore` — driving a turn on a task nobody's connection owns."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing

from harness.bots import BotStore
from harness.runtime.service import Runtime
from harness.session.log import Session
from harness.session.models import BotInstructionsEvent
from harness.session.service import SessionService
from harness.tools.approval import Approved
from harness.tools.definition import Failure, Ok

logger = logging.getLogger("harness.runs")


class RunAlreadyActive(RuntimeError):
    """This conversation is already running a turn."""


class Run:
    """One turn in flight, and the log it is writing into."""

    def __init__(self, session: Session, first_event_number: int) -> None:
        self.session = session
        self.first_event_number = first_event_number
        self.settled = False
        self.error: Exception | None = None
        self.condition = asyncio.Condition()
        self._inner: asyncio.Task[None] | None = None
        self._outer: asyncio.Task[None] | None = None

    @property
    def conversation_id(self) -> str:
        """The session's id."""
        return self.session.id


class RunStore:
    """Starts and stops turns, and knows which conversations are busy."""

    def __init__(self, service: SessionService, runtime: Runtime, bots: BotStore) -> None:
        self._service = service
        self._runtime = runtime
        self._bots = bots
        self._runs: dict[str, Run] = {}

    def active(self, conversation_id: str) -> Run | None:
        """The run in flight for this conversation, if any."""
        return self._runs.get(conversation_id)

    def start(self, session: Session, prompt: str) -> Run:
        """Begin a turn on a task this store owns."""
        if session.id in self._runs:
            raise RunAlreadyActive(session.id)
        self._log_instructions(session)
        run = Run(session, session.next_number())
        self._runs[session.id] = run
        run._inner = asyncio.create_task(
            self._stream(run, self._runtime.run(prompt, session=session))
        )
        run._outer = asyncio.create_task(self._drive(run))
        return run

    def resume(self, session: Session, call_id: str, outcome: Ok | Failure | Approved) -> Run:
        """Begin the turn that answers a client tool — the person's answer as its first event."""
        if session.id in self._runs:
            raise RunAlreadyActive(session.id)
        run = Run(session, session.next_number())
        self._runs[session.id] = run
        run._inner = asyncio.create_task(
            self._stream(run, self._runtime.resume(call_id, outcome, session=session))
        )
        run._outer = asyncio.create_task(self._drive(run))
        return run

    def compact(self, session: Session) -> Run:
        """Begin a manual compaction as its own run — no model turn, just the compaction events."""
        if session.id in self._runs:
            raise RunAlreadyActive(session.id)
        run = Run(session, session.next_number())
        self._runs[session.id] = run
        run._inner = asyncio.create_task(self._stream(run, self._runtime.compact(session=session)))
        run._outer = asyncio.create_task(self._drive(run))
        return run

    def clear(self, session: Session) -> Run:
        """Begin wiping this chat as a run of its own, taking over from the turn in flight."""
        in_flight = self._runs.get(session.id)
        run = Run(session, session.next_number())
        self._runs[session.id] = run
        run._outer = asyncio.create_task(self._end_then_wipe(in_flight, run))
        return run

    async def stop(self, conversation_id: str) -> bool:
        """End a turn early."""
        run = self._runs.get(conversation_id)
        if run is None or run._inner is None:
            return False
        await self._end(run)
        return True

    async def aclose(self) -> None:
        """Stop every run, for a server shutting down."""
        for conversation_id in list(self._runs):
            await self.stop(conversation_id)

    def _log_instructions(self, session: Session) -> None:
        """Log the answering bot's instructions when they are not the ones logged last."""
        bot = self._bots.bot_for(session.id)
        answering = BotInstructionsEvent(name=bot.name, instructions=bot.instructions)
        if session.bot_instructions() != answering:
            session.append(answering)

    async def _end(self, run: Run) -> None:
        """Cancel `run`'s turn, if it has begun, and wait for the run to settle."""
        if run._inner is not None:
            run._inner.cancel()
        if run._outer is not None:
            await asyncio.shield(run._outer)

    async def _end_then_wipe(self, in_flight: Run | None, clearing: Run) -> None:
        """Own the clear: the run in flight ended and settled, then the wipe run as its turn."""
        if in_flight is not None:
            await self._end(in_flight)
        clearing._inner = asyncio.create_task(self._wipe(clearing))
        await self._drive(clearing)

    async def _wipe(self, run: Run) -> None:
        """Write the wiped log over the stored one, and show it to whoever watches `run`."""
        run.session = await self._service.clear(run.conversation_id)
        await self._wake(run)

    async def _stream(self, run: Run, turn: AsyncIterator[object]) -> None:
        """Drive the turn, waking subscribers as the log grows."""
        async with aclosing(turn) as events:
            async for _ in events:
                await self._wake(run)

    async def _drive(self, run: Run) -> None:
        """Own the turn's ending. This task is never cancelled — see `stop`."""
        assert run._inner is not None
        try:
            await run._inner
        except asyncio.CancelledError:
            pass
        except Exception as err:
            run.error = err
            logger.exception("run for conversation %s raised", run.conversation_id)
        finally:
            await self._settle(run)

    async def _settle(self, run: Run) -> None:
        """Make the turn durable, then release everyone waiting on it."""
        with contextlib.suppress(Exception):
            await self._service.flush(run.session)
        async with run.condition:
            run.settled = True
            run.condition.notify_all()
        if self._runs.get(run.conversation_id) is run:
            del self._runs[run.conversation_id]

    async def _wake(self, run: Run) -> None:
        async with run.condition:
            run.condition.notify_all()
