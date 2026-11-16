"""A bot's runtime as its tickets' workers run it, for tests of what a worker is offered."""

from __future__ import annotations

from pathlib import Path

from harness.runtime.service import Runtime
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.tools import NO_CHAT_GRANTS, no_tools_from_start
from harness.web.tickets_wiring import ticket_workers
from tests.unit.helpers import no_bots, no_skills


def worker_of(bot: Runtime) -> Runtime:
    """`bot`'s runtime as each ticket's worker runs it, the one offered code mode and work tools."""
    assert bot.tools is not None
    logs = SessionService(JsonlSessionRepository(Path("/nonexistent/cell-harness-workers")))
    return ticket_workers(
        bot.tools.tool_service,
        bot,
        logs,
        no_bots(logs),
        chat_grants=NO_CHAT_GRANTS,
        skills=no_skills(),
        offered_from_start=no_tools_from_start,
    ).runtime
