"""An app whose bots start tickets, for `test_web_tickets.py`."""

from __future__ import annotations

import functools
import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from harness.app_events import AppEventService
from harness.bots import MENTION_TURN_ORDER, BotRepository, BotService, GroupService
from harness.llm import StreamEvent
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.secrets import SecretService
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tickets.repository import TicketRepository
from harness.tickets.service import TicketService
from harness.tools import ApprovalService, Tool, ToolService, Toolset
from harness.tools.client import ClientToolService
from harness.tools.native.tickets import TICKET_NOTE, TICKET_ROUTE
from harness.web.runtime import CLIENT_TOOLS
from harness.web.tickets_wiring import attach_tickets, ticket_workers
from tests.integration.web_helpers import ASSISTANT_START
from tests.unit.fakes import OneModel, PerBotClient
from tests.unit.helpers import durable_service, heard_nowhere, no_approvals, no_images, no_skills
from tests.webapp import a_model_saved_in, web_app

WORKER_START = "You are a worker."

BotTools = Callable[[BotService, SecretService], Sequence[Tool]]


def no_bot_tools(bots: BotService, secrets: SecretService) -> Sequence[Tool]:
    """No tool beyond the tickets' own."""
    return ()


@dataclass(frozen=True)
class Ticketing:
    """An app whose bots can start tickets, and the parts a test reaches into."""

    client: httpx.AsyncClient
    model: PerBotClient
    tickets: TicketService
    worker_logs: SessionService


def ticketing_app(
    tmp_path,
    scripts: Mapping[str, Sequence[Sequence[StreamEvent]]],
    *,
    bot_tools: BotTools = no_bot_tools,
    approvals: ApprovalService | None = None,
) -> Ticketing:
    """Bots offered `ticket_route` and `bot_tools`, they and their workers answered by `scripts`."""
    model = PerBotClient(scripts)
    service = durable_service(tmp_path / "sessions")
    app_events = AppEventService()
    bots = BotService(
        BotRepository(tmp_path / "bots.json"),
        service,
        assistant_instructions=ASSISTANT_START,
        app_events=app_events,
    )
    approvals = approvals or no_approvals()
    secrets = a_model_saved_in(tmp_path)
    extra = bot_tools(bots, secrets)
    tool_service = ToolService(extra, approvals=approvals)
    offered = (TICKET_ROUTE, TICKET_NOTE, *(tool.name for tool in extra))
    runtime = Runtime(
        models=OneModel(model),
        images=no_images(),
        tools=Toolset(tool_service, offered, sight_tools=frozenset()),
        guidance="GUIDE",
        checkpoint=service.flush,
    )
    runs = RunService(
        service,
        runtime,
        bots,
        GroupService(bots, service, MENTION_TURN_ORDER),
        app_events=app_events,
    )
    worker_logs = SessionService(JsonlSessionRepository(tmp_path / "workers"))
    tickets = TicketService(
        TicketRepository(tmp_path / "tickets.json"),
        bots,
        runs,
        worker=ticket_workers(tool_service, runtime, worker_logs),
        logs=worker_logs,
        follow=heard_nowhere,
        now=lambda: datetime.now(UTC),
        ids=functools.partial(next, (f"t{n}" for n in itertools.count(1))),
    )
    attach_tickets(tool_service, tickets)
    app = web_app(
        tmp_path,
        service,
        runs,
        skills=no_skills(),
        client_tools=ClientToolService(CLIENT_TOOLS, approvals),
        approvals=approvals,
        bots=bots,
        secrets=secrets,
        tickets=tickets,
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return Ticketing(client, model, tickets, worker_logs)
