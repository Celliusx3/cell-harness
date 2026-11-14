"""The tickets the server composes: `ticket_route` for every bot, `ticket_report` for workers."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from harness.prompts import GUIDANCE
from harness.runtime.service import Runtime
from harness.session.service.session_service import SessionService
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import RuntimeTicketWorker
from harness.tools import ToolService
from harness.tools.native.files import VIEW_IMAGE
from harness.tools.native.tickets import (
    TICKET_REPORT,
    ticket_note_tool,
    ticket_report_tool,
    ticket_route_tool,
)
from harness.tools.service.tool_service import Disposer
from harness.web.runtime import SUBAGENT_TOOLS, WORK_TOOLS, delegate_runtime

WORKER_TOOLS = (*SUBAGENT_TOOLS, *WORK_TOOLS, VIEW_IMAGE, TICKET_REPORT)


def ticket_workers(
    tool_service: ToolService,
    runtime: Runtime,
    logs: SessionService,
    bot_chat_id: Callable[[str], str],
) -> RuntimeTicketWorker:
    """`runtime` as each ticket's worker runs it, in its bot's chat, its logs in `logs`."""
    worker = dataclasses.replace(
        delegate_runtime(tool_service, runtime, WORKER_TOOLS),
        guidance=GUIDANCE,
        chat_id_for=lambda _session, bot_id: bot_chat_id(bot_id),
    )
    return RuntimeTicketWorker(worker, logs)


def attach_tickets(tool_service: ToolService, tickets: TicketService) -> Disposer:
    """`ticket_route`, `ticket_note` and `ticket_report` offered from `tool_service`."""
    return tool_service.add_provider(
        lambda: [ticket_route_tool(tickets), ticket_note_tool(tickets), ticket_report_tool()]
    )
