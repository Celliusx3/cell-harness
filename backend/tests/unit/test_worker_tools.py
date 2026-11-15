"""A ticket's worker reports, and starts no helpers: the worker is the only one doing the work."""

from __future__ import annotations

from pathlib import Path

from harness.config.settings import Settings
from harness.mcp import McpService
from harness.runtime.service import Runtime
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.tickets.domain.prompts import WORKER_INTRO
from harness.tools import NO_CHAT_GRANTS
from harness.tools.native.tickets import TICKET_REPORT
from harness.web.runtime import build_runtime
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


def test_a_worker_offers_its_report_and_no_helpers(
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

    worker = offered(
        ticket_workers(tool_service, runtime, logs, bots, chat_grants=NO_CHAT_GRANTS).runtime
    )

    assert TICKET_REPORT in worker
    assert "run_subagent" not in worker | offered(runtime)


def test_a_worker_is_not_told_to_split_its_ticket_across_helpers() -> None:
    assert "run_subagent" not in WORKER_INTRO
    assert "helper" not in WORKER_INTRO
