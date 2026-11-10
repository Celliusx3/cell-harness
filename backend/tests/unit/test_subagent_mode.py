"""A subagent takes the chat's mode when it starts: Auto runs a protected call, Ask stops at it."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.runtime.subagents import Subagents
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools import ApprovalMode, ApprovalService, CallOrigin, Ok, Tool, ToolContext
from harness.tools.native.subagent import (
    SubagentReply,
    SubagentStop,
    SubagentTask,
    run_subagent_tool,
)
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.helpers import no_progress, runtime_over

TASK = SubagentTask(name="notes", task="Save the note Kopi.")
SAVE = "save_note"


@pytest.fixture
def sessions(tmp_path: Path) -> SessionService:
    return SessionService(JsonlSessionRepository(tmp_path))


def _subagents(sessions: SessionService, tmp_path: Path, ran: list[str]) -> Subagents:
    async def execute(args: EchoArgs, _context) -> Ok:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    saver = Tool.from_model(name=SAVE, description="Save.", args_model=EchoArgs, execute=execute)
    approvals = ApprovalService(
        frozenset({SAVE}), frozenset, tmp_path / "approvals.json", default_mode="ask"
    )
    client = SteppedClient(calls_tool(SAVE, '{"value": "Kopi"}'), completed("saved"))
    return Subagents(runtime_over(client, saver, approvals=approvals), sessions)


async def test_a_subagent_started_in_auto_runs_a_protected_call(
    sessions: SessionService, tmp_path: Path
) -> None:
    ran: list[str] = []

    outcome = await _subagents(sessions, tmp_path, ran)("c.0", TASK, bot_id="b", mode="auto")

    assert outcome == SubagentReply(text="saved")
    assert ran == ["Kopi"]


async def test_a_subagent_started_in_ask_stops_at_a_protected_call(
    sessions: SessionService, tmp_path: Path
) -> None:
    ran: list[str] = []

    outcome = await _subagents(sessions, tmp_path, ran)("c.0", TASK, bot_id="b", mode="ask")

    assert isinstance(outcome, SubagentStop)
    assert "needs the user" in outcome.reason
    assert ran == []


async def test_the_tool_starts_each_subagent_in_the_calling_chat_mode() -> None:
    modes: list[ApprovalMode] = []

    async def runner(_subagent_id: str, _task: SubagentTask, *, bot_id: str, mode: ApprovalMode):
        modes.append(mode)
        return SubagentReply(text="ok")

    origin = CallOrigin(bot_id="b", conversation_id="chat", mode="auto")
    context = ToolContext(call_id="call-1", progress=no_progress, origin=origin)
    await run_subagent_tool(runner).invoke(
        '{"tasks": [{"name": "a", "task": "x"}, {"name": "b", "task": "y"}]}', context=context
    )

    assert modes == ["auto", "auto"]
