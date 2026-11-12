"""The bot never asks the person itself: a missing detail is a worker's question, in its report."""

from __future__ import annotations

from pathlib import Path

from harness.config.settings import Settings
from harness.mcp import McpService
from harness.runtime.service import Runtime
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools.native.tickets import TICKET_ROUTE
from harness.web.runtime import CLIENT_TOOLS, build_runtime
from harness.web.tickets_wiring import attach_tickets, ticket_workers
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import (
    client_tools,
    no_approvals,
    no_bots,
    no_skills,
    no_tickets,
    run_service,
)
from tests.webapp import files_in, images_in, secrets_in


def offered(runtime: Runtime) -> set[str]:
    assert runtime.tools is not None
    return {spec.name for spec in runtime.tools.specs(sees_images=True)}


def test_neither_the_bot_nor_its_workers_offer_a_client_tool_yet_each_stays_registered(
    tmp_path: Path,
) -> None:
    bots = no_bots(SessionService(JsonlSessionRepository(tmp_path / "bot-chats")))
    logs = SessionService(JsonlSessionRepository(tmp_path / "subagents"))
    runtime = build_runtime(
        Settings(),
        SessionService(JsonlSessionRepository(tmp_path)),
        McpService({}),
        no_skills(),
        client_tools(),
        no_approvals(),
        bots=bots,
        subagent_logs=logs,
        secrets=secrets_in(tmp_path),
        images=images_in(tmp_path),
        files=files_in(tmp_path),
    )
    assert runtime.tools is not None
    tool_service = runtime.tools.tool_service
    runs = run_service(
        SessionService(JsonlSessionRepository(tmp_path / "runs")), ScriptedClient([])
    )
    attach_tickets(tool_service, no_tickets(tmp_path, bots, runs))

    bot = offered(runtime)
    worker = offered(ticket_workers(tool_service, runtime, logs).runtime)

    assert TICKET_ROUTE in bot
    assert not CLIENT_TOOLS.names & bot
    assert not CLIENT_TOOLS.names & worker
    assert all(tool_service.get(name) is not None for name in CLIENT_TOOLS.names)
