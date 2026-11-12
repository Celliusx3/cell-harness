"""Tickets: each saved, worked on in the background, its result told to the bot that began it."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from harness.app_events import TicketsChangedAppEvent
from harness.bots import BotNotFound, BotService
from harness.runs.run import Run
from harness.runs.service import RunService
from harness.session.models import SessionEvent, TicketReport
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.tickets.models import (
    NEEDS_YOU,
    RETRYABLE,
    AskedKey,
    Ticket,
    TicketNotAsking,
    TicketNotFound,
    TicketNotRetryable,
    TicketsFile,
    TicketState,
    TicketStopped,
    ticket_state,
)
from harness.tickets.places import Places
from harness.tickets.prompts import TICKET_ANSWER_HEARD, TICKET_RECOVERY_HEARD, TICKET_RETRY_HEARD
from harness.tickets.repository import TicketRepository
from harness.tickets.worker import WorkerEnd, kept_report, worker_end, worker_session_id
from harness.tools.models.decision import ApprovalMode

logger = logging.getLogger("harness.tickets")

Follow = Callable[[Run], Awaitable[None]]
WorkerTurn = Callable[[], Awaitable[WorkerEnd]]


class TicketWorker(Protocol):
    """Runs a ticket's first turn in `mode`, and each next turn on the same log, to its end."""

    async def start(self, ticket: Ticket, *, mode: ApprovalMode) -> WorkerEnd: ...

    async def resume(self, ticket: Ticket, prompt: str) -> WorkerEnd: ...


class TicketService:
    """Saves each ticket, runs its worker on a task it owns, and delivers the worker's end."""

    def __init__(
        self,
        repository: TicketRepository,
        bots: BotService,
        runs: RunService,
        *,
        worker: TicketWorker,
        logs: SessionService,
        follow: Follow,
        now: Callable[[], datetime],
        ids: Callable[[], str],
    ) -> None:
        self._repository = repository
        self._bots = bots
        self._runs = runs
        self._worker = worker
        self._logs = logs
        self._follow = follow
        self._now = now
        self._ids = ids
        self._locks: dict[str, asyncio.Lock] = {}
        self._working: set[asyncio.Task[None]] = set()
        self._running: set[str] = set()
        self._places = Places(lambda bot_id: bots.active_bot(bot_id).max_workers)

    def of_bot(self, bot_id: str) -> tuple[Ticket, ...]:
        """`bot_id`'s tickets, in the order started."""
        return tuple(t for t in self._repository.read().tickets if t.bot_id == bot_id)

    def needing_you(self) -> tuple[Ticket, ...]:
        """Every bot's tickets that wait for a person, oldest first."""
        waiting = (t for t in self._repository.read().tickets if t.state in NEEDS_YOU)
        return tuple(sorted(waiting, key=lambda t: t.created_at))

    def get(self, ticket_id: str) -> Ticket:
        """The ticket with this id; `TicketNotFound` when there is none."""
        found = next((t for t in self._repository.read().tickets if t.id == ticket_id), None)
        if found is None:
            raise TicketNotFound(ticket_id)
        return found

    def is_running(self, ticket_id: str) -> bool:
        """Whether `ticket_id`'s worker is in flight now."""
        return ticket_id in self._running

    async def worker_events(self, ticket_id: str) -> tuple[SessionEvent, ...]:
        """What `ticket_id`'s worker has logged so far; none before it writes anything."""
        try:
            session = await self._logs.read(worker_session_id(ticket_id))
        except SessionNotFoundError:
            return ()
        return tuple(session.events())

    def accept(self, *, bot_id: str, title: str, task: str, mode: ApprovalMode) -> Ticket:
        """A new `working` ticket for `bot_id`, saved, its worker started in the background."""
        ticket = Ticket(
            id=self._ids(),
            bot_id=bot_id,
            title=title,
            task=task,
            state="working",
            created_at=self._now(),
            mode=mode,
        )
        stored = self._repository.read()
        self._save(TicketsFile(tickets=(*stored.tickets, ticket)))
        self._start_first(ticket)
        return ticket

    def recover(self) -> None:
        """After a restart, resume each working ticket with a note and start each queued one."""
        for ticket in sorted(self._repository.read().tickets, key=lambda t: t.created_at):
            if ticket.state == "working":
                self._tell(ticket.id, TICKET_RECOVERY_HEARD, answer=False)
            elif ticket.state == "queued":
                self._start_first(ticket)

    def _start_first(self, ticket: Ticket) -> None:
        self._start(ticket, lambda: self._worker.start(ticket, mode=ticket.mode), answer=False)

    def answer(self, ticket_id: str, text: str) -> None:
        """Send the person's answer to the ticket's question; `TicketNotAsking` if it asks none."""
        if self.get(ticket_id).state != "needs_answer":
            raise TicketNotAsking(ticket_id)
        self._tell(ticket_id, TICKET_ANSWER_HEARD.format(text=text), answer=True)

    async def asks_for_key(self, ticket_id: str) -> bool:
        """Whether the ticket's question waits for a key, which only its secret box may answer."""
        try:
            await self.asked_key(ticket_id)
        except TicketNotAsking:
            return False
        return True

    async def asked_key(self, ticket_id: str) -> AskedKey:
        """The key the ticket's question waits for; `TicketNotAsking` unless it asks for one."""
        ticket = self.get(ticket_id)
        asking = ticket.state == "needs_answer"
        kept = kept_report(await self.worker_events(ticket_id)) if asking else None
        if kept is None or kept.secret_name is None or kept.secret_destination is None:
            raise TicketNotAsking(ticket_id)
        return AskedKey(
            bot_id=ticket.bot_id, name=kept.secret_name, destination=kept.secret_destination
        )

    def retry(self, ticket_id: str) -> None:
        """Run a blocked or failed ticket's worker again; `TicketNotRetryable` for any other."""
        if self.get(ticket_id).state not in RETRYABLE:
            raise TicketNotRetryable(ticket_id)
        self._tell(ticket_id, TICKET_RETRY_HEARD, answer=False)

    def tell(self, ticket_id: str, prompt: str) -> None:
        """Run the worker's next turn on `prompt` once its turn ends; `TicketStopped` if stopped."""
        self._tell(ticket_id, prompt, answer=False)

    def _tell(self, ticket_id: str, prompt: str, *, answer: bool) -> None:
        ticket = self.get(ticket_id)
        if ticket.state == "stopped":
            raise TicketStopped(ticket_id)
        self._set_state(ticket.id, "working")
        self._start(ticket, lambda: self._worker.resume(ticket, prompt), answer=answer)

    def stop(self, ticket_id: str) -> None:
        """End the ticket for good and cancel its turns; `TicketStopped` if it already is."""
        if self.get(ticket_id).state == "stopped":
            raise TicketStopped(ticket_id)
        self._set_state(ticket_id, "stopped")
        for task in list(self._working):
            if task.get_name() == ticket_id:
                task.cancel()

    async def aclose(self) -> None:
        """Cancel every worker still running, for a server shutting down."""
        for task in list(self._working):
            task.cancel()
        await asyncio.gather(*self._working, return_exceptions=True)

    def _start(self, ticket: Ticket, turn: WorkerTurn, *, answer: bool) -> None:
        running = asyncio.create_task(self._work(ticket, turn, answer=answer), name=ticket.id)
        self._working.add(running)
        running.add_done_callback(self._working.discard)

    async def _work(self, ticket: Ticket, turn: WorkerTurn, *, answer: bool) -> None:
        """One turn of `ticket`'s worker, its end told to the bot, unless stopped or dropped."""
        end = await self._locked_turn(ticket, turn, answer=answer)
        if end is None or end.state == "dropped":
            return
        report = TicketReport(
            ticket_id=ticket.id,
            title=ticket.title,
            state=end.state,
            text=end.text,
            question=end.question,
            ask=end.ask,
            options=end.options,
            secret_name=end.secret_name,
        )
        await self._deliver(ticket.bot_id, report)

    async def _locked_turn(
        self, ticket: Ticket, turn: WorkerTurn, *, answer: bool
    ) -> WorkerEnd | None:
        """The turn's end, run after the one before it and kept; `None` for a stopped ticket."""
        async with self._locks.setdefault(ticket.id, asyncio.Lock()):
            if self._is_stopped(ticket.id):
                return None
            try:
                end = await self._placed_turn(ticket, turn, answer=answer)
            except BotNotFound:
                logger.warning("ticket %s failed: its bot %s is gone", ticket.id, ticket.bot_id)
                end = worker_end(None, None)
            if self._is_stopped(ticket.id):
                return None
            self._set_state(ticket.id, ticket_state(end.state, end.question))
            return end

    async def _placed_turn(self, ticket: Ticket, turn: WorkerTurn, *, answer: bool) -> WorkerEnd:
        """The turn run in one of its bot's places, `queued` until it has one."""
        queued = functools.partial(self._set_state, ticket.id, "queued")
        async with self._places.place(ticket.bot_id, answer=answer, on_wait=queued):
            self._set_state(ticket.id, "working")
            self._running.add(ticket.id)
            try:
                return await self._run_worker(ticket, turn)
            finally:
                self._running.discard(ticket.id)

    def _is_stopped(self, ticket_id: str) -> bool:
        return self.get(ticket_id).state == "stopped"

    async def _run_worker(self, ticket: Ticket, turn: WorkerTurn) -> WorkerEnd:
        """The turn's end; `failed` with the error logged when the worker itself broke."""
        try:
            return await turn()
        except Exception:
            logger.exception("the worker of ticket %s broke", ticket.id)
            return worker_end(None, None)

    def _set_state(self, ticket_id: str, state: TicketState) -> None:
        stored = self._repository.read()
        tickets = tuple(
            t.model_copy(update={"state": state}) if t.id == ticket_id else t
            for t in stored.tickets
        )
        self._save(TicketsFile(tickets=tickets))

    def _save(self, stored: TicketsFile) -> None:
        """Write every ticket, and tell the app's pages that tickets changed."""
        self._repository.write(stored)
        self._runs.app_events.publish(TicketsChangedAppEvent())

    async def _deliver(self, bot_id: str, report: TicketReport) -> None:
        """The turn `report` opens in `bot_id`'s own chat once free, heard by its chat apps."""
        try:
            run = await self._runs.hear_when_free(self._bots.chat_of(bot_id), report)
        except (BotNotFound, SessionNotFoundError) as err:
            logger.warning("ticket report dropped, nobody is left to hear it: %s", err)
            return
        await self._follow(run)
