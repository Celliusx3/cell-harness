"""The tickets the server composes: `ticket_accept` for every bot, `ticket_report` for workers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from harness.bots import BotService
from harness.runs.bot_messages import Follow
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.session.service import SessionService
from harness.tickets.repository import TicketRepository
from harness.tickets.service import TicketService
from harness.tickets.worker import Workers
from harness.tools import ToolService
from harness.tools.native.tickets import (
    TICKET_REPORT,
    ticket_accept_tool,
    ticket_note_tool,
    ticket_report_tool,
)
from harness.web.runtime import SUBAGENT_TOOLS, helper_runtime

WORKER_TOOLS = (*SUBAGENT_TOOLS, TICKET_REPORT)


def attach_tickets(
    tool_service: ToolService,
    runtime: Runtime,
    bots: BotService,
    runs: RunService,
    *,
    logs: SessionService,
    repository: TicketRepository,
    follow: Follow,
    now: Callable[[], datetime],
    ids: Callable[[], str],
) -> TicketService:
    """`ticket_accept`, `ticket_note` and `ticket_report` offered, run by the service returned."""
    workers = Workers(helper_runtime(tool_service, runtime, WORKER_TOOLS), logs)
    tickets = TicketService(
        repository, bots, runs, worker=workers, logs=logs, follow=follow, now=now, ids=ids
    )
    tool_service.add_provider(
        lambda: [ticket_accept_tool(tickets), ticket_note_tool(tickets), ticket_report_tool()]
    )
    return tickets
