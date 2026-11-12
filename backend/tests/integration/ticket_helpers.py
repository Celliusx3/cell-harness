"""An app whose bots start tickets, for `test_web_tickets.py`."""

from __future__ import annotations

import functools
import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from harness.app_events import AppEventService
from harness.bots import BotService
from harness.llm import StreamEvent
from harness.runs.service import RunService
from harness.runtime.service import Runtime
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tickets.repository import TicketRepository
from harness.tickets.service import TicketService
from harness.tools import ToolService, Toolset
from harness.tools.native.tickets import TICKET_NOTE, TICKET_ROUTE
from harness.web.tickets_wiring import attach_tickets
from tests.integration.web_helpers import ASSISTANT_START
from tests.unit.fakes import OneModel, PerBotClient
from tests.unit.helpers import durable_service, heard_nowhere, no_approvals, no_images, no_skills
from tests.webapp import a_model_saved_in, web_app

WORKER_START = "You are a worker."


@dataclass(frozen=True)
class Ticketing:
    """An app whose bots can start tickets, and the parts a test reaches into."""

    client: httpx.AsyncClient
    model: PerBotClient
    tickets: TicketService
    worker_logs: SessionService


def ticketing_app(tmp_path, scripts: Mapping[str, Sequence[Sequence[StreamEvent]]]) -> Ticketing:
    """Assistant offered `ticket_route`, it and its workers answered from `scripts`."""
    model = PerBotClient(scripts)
    service = durable_service(tmp_path / "sessions")
    app_events = AppEventService()
    bots = BotService(
        tmp_path / "bots.json",
        service,
        assistant_instructions=ASSISTANT_START,
        app_events=app_events,
    )
    tool_service = ToolService([], approvals=no_approvals())
    runtime = Runtime(
        models=OneModel(model),
        images=no_images(),
        tools=Toolset(tool_service, (TICKET_ROUTE, TICKET_NOTE), sight_tools=frozenset()),
        guidance="GUIDE",
        checkpoint=service.flush,
    )
    runs = RunService(service, runtime, bots, app_events=app_events)
    worker_logs = SessionService(JsonlSessionRepository(tmp_path / "workers"))
    tickets = attach_tickets(
        tool_service,
        runtime,
        bots,
        runs,
        logs=worker_logs,
        repository=TicketRepository(tmp_path / "tickets.json"),
        follow=heard_nowhere,
        now=lambda: datetime.now(UTC),
        ids=functools.partial(next, (f"t{n}" for n in itertools.count(1))),
    )
    secrets = a_model_saved_in(tmp_path)
    app = web_app(
        tmp_path, service, runs, skills=no_skills(), bots=bots, secrets=secrets, tickets=tickets
    )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    return Ticketing(client, model, tickets, worker_logs)
