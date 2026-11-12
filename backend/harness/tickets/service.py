"""Tickets: each saved, worked on in the background, its result told to the bot that began it."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from harness.bots import BotNotFound, BotService
from harness.runs.run import Run
from harness.runs.service import RunService
from harness.session.models import TicketReport
from harness.session.repository import SessionNotFoundError
from harness.tickets.models import Ticket, TicketsFile, TicketState, ticket_state
from harness.tickets.repository import TicketRepository
from harness.tickets.worker import WorkerEnd, worker_end
from harness.tools.models.decision import ApprovalMode

logger = logging.getLogger("harness.tickets")

Follow = Callable[[Run], Awaitable[None]]


class TicketWorker(Protocol):
    """Runs `ticket`'s task for its bot in `mode` to its end."""

    async def __call__(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd: ...


class TicketService:
    """Saves each ticket, runs its worker on a task it owns, and delivers the worker's end."""

    def __init__(
        self,
        repository: TicketRepository,
        bots: BotService,
        runs: RunService,
        *,
        worker: TicketWorker,
        follow: Follow,
        now: Callable[[], datetime],
    ) -> None:
        self._repository = repository
        self._bots = bots
        self._runs = runs
        self._worker = worker
        self._follow = follow
        self._now = now
        self._working: set[asyncio.Task[None]] = set()

    def of_bot(self, bot_id: str) -> tuple[Ticket, ...]:
        """`bot_id`'s tickets, in the order started."""
        return tuple(t for t in self._repository.read().tickets if t.bot_id == bot_id)

    def accept(self, *, bot_id: str, title: str, task: str, mode: ApprovalMode) -> Ticket:
        """A new `working` ticket for `bot_id`, saved, its worker started in the background."""
        ticket = Ticket(
            id=uuid.uuid4().hex,
            bot_id=bot_id,
            title=title,
            task=task,
            state="working",
            created_at=self._now(),
        )
        stored = self._repository.read()
        self._repository.write(TicketsFile(tickets=(*stored.tickets, ticket)))
        running = asyncio.create_task(self._work(ticket, mode))
        self._working.add(running)
        running.add_done_callback(self._working.discard)
        return ticket

    async def aclose(self) -> None:
        """Cancel every worker still running, for a server shutting down."""
        for task in list(self._working):
            task.cancel()
        await asyncio.gather(*self._working, return_exceptions=True)

    async def _work(self, ticket: Ticket, mode: ApprovalMode) -> None:
        """Run `ticket`'s worker, keep how it ended, then tell the bot."""
        end = await self._run_worker(ticket, mode)
        self._set_state(ticket.id, ticket_state(end.state, end.question))
        report = TicketReport(
            ticket_id=ticket.id,
            title=ticket.title,
            state=end.state,
            text=end.text,
            question=end.question,
        )
        await self._deliver(ticket.bot_id, report)

    async def _run_worker(self, ticket: Ticket, mode: ApprovalMode) -> WorkerEnd:
        """The worker's end; `failed` with the error logged when the worker itself broke."""
        try:
            return await self._worker(ticket, mode=mode)
        except Exception:
            logger.exception("the worker of ticket %s broke", ticket.id)
            return worker_end(None, None)

    def _set_state(self, ticket_id: str, state: TicketState) -> None:
        stored = self._repository.read()
        tickets = tuple(
            t.model_copy(update={"state": state}) if t.id == ticket_id else t
            for t in stored.tickets
        )
        self._repository.write(TicketsFile(tickets=tickets))

    async def _deliver(self, bot_id: str, report: TicketReport) -> None:
        """The turn `report` opens in `bot_id`'s own chat once free, heard by its chat apps."""
        try:
            run = await self._runs.hear_when_free(self._bots.chat_of(bot_id), report)
        except (BotNotFound, SessionNotFoundError) as err:
            logger.warning("ticket report dropped, nobody is left to hear it: %s", err)
            return
        await self._follow(run)
