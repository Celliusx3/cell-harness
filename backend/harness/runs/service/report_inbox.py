"""Where a goal run hears its team's ticket reports: handed over by delivery, inside the run."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import NamedTuple

from harness.session.domain.models import TicketReport


class _Handed(NamedTuple):
    report: TicketReport
    heard: asyncio.Future[bool]


class ReportInbox:
    """The tickets a goal run's team routed in it, and each report handed over for one."""

    def __init__(self) -> None:
        self._routed: dict[str, str] = {}
        self._handed: dict[str, _Handed] = {}
        self._changed = asyncio.Event()

    def expect(self, ticket_id: str, bot_id: str) -> None:
        """Have the report of `bot_id`'s ticket `ticket_id` heard in the run."""
        self._routed[ticket_id] = bot_id

    async def hand_over(self, report: TicketReport) -> bool:
        """Whether the run heard `report`; `False` at once for a ticket it does not wait for."""
        if report.ticket_id not in self._routed:
            return False
        handed = _Handed(report, asyncio.get_running_loop().create_future())
        self._handed[report.ticket_id] = handed
        self._changed.set()
        try:
            return await handed.heard
        finally:
            if self._handed.get(report.ticket_id) is handed:
                del self._handed[report.ticket_id]

    async def next_for(self, bot_id: str) -> TicketReport | None:
        """The next report handed over for `bot_id`'s tickets; `None` once none is awaited."""
        while True:
            handed = next(
                (h for ticket, h in self._handed.items() if self._routed.get(ticket) == bot_id),
                None,
            )
            if handed is not None:
                return self._take(handed)
            if bot_id not in self._routed.values():
                return None
            self._changed.clear()
            await self._changed.wait()

    def release(self, bot_id: str) -> None:
        """Stop waiting for `bot_id`'s tickets: their reports are heard after the run."""
        for ticket_id in [t for t, bot in self._routed.items() if bot == bot_id]:
            self.forget(ticket_id)

    def forget(self, ticket_id: str) -> None:
        """Stop waiting for `ticket_id`; a report already handed over is heard after the run."""
        self._routed.pop(ticket_id, None)
        handed = self._handed.pop(ticket_id, None)
        if handed is not None and not handed.heard.done():
            handed.heard.set_result(False)
        self._changed.set()

    def close(self) -> None:
        """Stop waiting for every ticket, for a run that ended."""
        for ticket_id in list(self._routed):
            self.forget(ticket_id)

    def _take(self, handed: _Handed) -> TicketReport:
        ticket_id = handed.report.ticket_id
        del self._routed[ticket_id]
        del self._handed[ticket_id]
        if not handed.heard.done():
            handed.heard.set_result(True)
        return handed.report


class ReportInboxes:
    """Each chat's inbox while a goal run in it waits for its team's reports."""

    def __init__(self) -> None:
        self._open: dict[str, ReportInbox] = {}

    @contextmanager
    def opened(self, chat_id: str) -> Iterator[ReportInbox]:
        """`chat_id`'s inbox for as long as its goal run lasts, closed when it ends."""
        inbox = ReportInbox()
        self._open[chat_id] = inbox
        try:
            yield inbox
        finally:
            inbox.close()
            if self._open.get(chat_id) is inbox:
                del self._open[chat_id]

    def expect(self, chat_id: str, ticket_id: str, bot_id: str) -> None:
        """Have `ticket_id`'s report heard in `chat_id`'s goal run; nothing when none runs."""
        inbox = self._open.get(chat_id)
        if inbox is not None:
            inbox.expect(ticket_id, bot_id)

    async def hand_over(self, chat_id: str, report: TicketReport) -> bool:
        """Whether `chat_id`'s goal run heard `report`; `False` for one it does not wait for."""
        inbox = self._open.get(chat_id)
        return inbox is not None and await inbox.hand_over(report)

    def withdraw(self, ticket_id: str) -> None:
        """No goal run waits for `ticket_id` any more: it ends with no report."""
        for inbox in self._open.values():
            inbox.forget(ticket_id)
