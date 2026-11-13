"""A ticket's worker: its first turn takes the chat's mode, and each next turn keeps it."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harness.llm import SystemMessage
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tickets.domain.models import Ticket
from harness.tickets.service.worker import WorkerEnd, Workers, worker_session_id
from harness.tools import ApprovalService, Ok, Tool
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.helpers import runtime_over

SAVE = "save_note"
TICKET = Ticket(
    id="t1",
    bot_id="b",
    title="Notes",
    task="Wait for the note.",
    state="working",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
)


def workers(tmp_path: Path, ran: list[str]) -> tuple[Workers, SteppedClient, SessionService]:
    async def execute(args: EchoArgs, _context) -> Ok:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    saver = Tool.from_model(name=SAVE, description="Save.", args_model=EchoArgs, execute=execute)
    approvals = ApprovalService(
        frozenset({SAVE}), frozenset, tmp_path / "approvals.json", default_mode="ask"
    )
    client = SteppedClient(
        completed("Waiting."), calls_tool(SAVE, '{"value": "Kopi"}'), completed("Saved.")
    )
    sessions = SessionService(JsonlSessionRepository(tmp_path / "workers"))
    runtime = runtime_over(client, saver, approvals=approvals, guidance="BASE")
    return Workers(runtime, sessions), client, sessions


async def test_a_resumed_turn_keeps_the_mode_its_first_turn_logged(tmp_path: Path) -> None:
    ran: list[str] = []
    each, client, sessions = workers(tmp_path, ran)

    first = await each.start(TICKET, mode="auto")
    then = await each.resume(TICKET, "The note is Kopi.")

    assert first == WorkerEnd(state="ready", text="Waiting.", question=None)
    assert then == WorkerEnd(state="ready", text="Saved.", question=None)
    assert ran == ["Kopi"]
    systems = [m for call in client.seen_per_call for m in call if isinstance(m, SystemMessage)]
    assert all(m.content.startswith("You are a worker.") and "BASE" in m.content for m in systems)
    stored = await sessions.read(worker_session_id(TICKET.id))
    assert [e.message.content for e in stored.events() if e.type == "user/message"] == [
        "Wait for the note.",
        "The note is Kopi.",
    ]
