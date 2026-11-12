"""The tickets the server composes: `ticket_route` for every bot, `ticket_report` for workers."""

from __future__ import annotations

from harness.runtime.service import Runtime
from harness.session.service import SessionService
from harness.tickets.service import TicketService
from harness.tickets.worker import Workers
from harness.tools import ToolService
from harness.tools.native.tickets import (
    TICKET_REPORT,
    ticket_note_tool,
    ticket_report_tool,
    ticket_route_tool,
)
from harness.tools.service import Disposer
from harness.web.runtime import SUBAGENT_TOOLS, helper_runtime

WORKER_TOOLS = (*SUBAGENT_TOOLS, TICKET_REPORT)


def ticket_workers(tool_service: ToolService, runtime: Runtime, logs: SessionService) -> Workers:
    """`runtime` as each ticket's worker runs it, offered `WORKER_TOOLS`, its logs in `logs`."""
    return Workers(helper_runtime(tool_service, runtime, WORKER_TOOLS), logs)


def attach_tickets(tool_service: ToolService, tickets: TicketService) -> Disposer:
    """`ticket_route`, `ticket_note` and `ticket_report` offered from `tool_service`."""
    return tool_service.add_provider(
        lambda: [ticket_route_tool(tickets), ticket_note_tool(tickets), ticket_report_tool()]
    )
