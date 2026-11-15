"""The tickets the server composes: `ticket_route` for every bot, `ticket_report` for workers."""

from __future__ import annotations

import dataclasses
from typing import Protocol

from harness.bots import Bot
from harness.prompts import GUIDANCE
from harness.runtime.service import Runtime
from harness.session.service.session_service import SessionService
from harness.tickets.service.ticket_service import TicketService
from harness.tickets.service.worker import RuntimeTicketWorker
from harness.tools import ChatGrants, ToolService
from harness.tools.native.files import VIEW_IMAGE
from harness.tools.native.tickets import (
    TICKET_REPORT,
    ticket_note_tool,
    ticket_report_tool,
    ticket_route_tool,
)
from harness.tools.service.tool_service import Disposer
from harness.web.runtime import CODE_TOOLS, SKILL_WRITE_TOOLS, WORK_TOOLS, delegate_runtime

WORKER_TOOLS = (*CODE_TOOLS, *WORK_TOOLS, *SKILL_WRITE_TOOLS, VIEW_IMAGE, TICKET_REPORT)


class BotLookup(Protocol):
    """A bot's chat and its settings, as a ticket's worker needs them."""

    def chat_of(self, bot_id: str) -> str: ...

    def active_bot(self, bot_id: str) -> Bot: ...


def ticket_workers(
    tool_service: ToolService,
    runtime: Runtime,
    logs: SessionService,
    bots: BotLookup,
    *,
    chat_grants: ChatGrants,
) -> RuntimeTicketWorker:
    """`runtime` as each ticket's worker runs it, in its bot's chat and under its grants."""
    worker = dataclasses.replace(
        delegate_runtime(tool_service, runtime, WORKER_TOOLS, chat_grants),
        guidance=GUIDANCE,
        chat_id_for=lambda _session, bot_id: bots.chat_of(bot_id),
    )
    return RuntimeTicketWorker(worker, logs, lambda bot_id: bots.active_bot(bot_id).max_workers)


def attach_tickets(tool_service: ToolService, tickets: TicketService) -> Disposer:
    """`ticket_route`, `ticket_note` and `ticket_report` offered from `tool_service`."""
    return tool_service.add_provider(
        lambda: [ticket_route_tool(tickets), ticket_note_tool(tickets), ticket_report_tool()]
    )
