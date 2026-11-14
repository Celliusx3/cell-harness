"""A ticket's worker may start subagents and report; its subagents may do neither."""

from __future__ import annotations

from pathlib import Path

from harness.config.settings import Settings
from harness.mcp import McpService
from harness.runtime.service import Runtime
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.tools.native.subagent import RUN_SUBAGENT
from harness.tools.native.tickets import TICKET_REPORT
from harness.web.runtime import SUBAGENT_TOOLS, build_runtime, delegate_runtime
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


def test_a_worker_offers_subagents_and_its_report_and_a_subagent_offers_neither(
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

    worker = offered(ticket_workers(tool_service, runtime, logs, bots.chat_of).runtime)
    subagent = offered(delegate_runtime(tool_service, runtime, SUBAGENT_TOOLS))

    assert {RUN_SUBAGENT, TICKET_REPORT} <= worker
    assert not {RUN_SUBAGENT, TICKET_REPORT} & subagent
