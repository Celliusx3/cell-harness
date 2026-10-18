"""One subagent: its own log under the id it was given, and how its turn ending is reported."""

from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from harness.llm import Failed, SystemMessage
from harness.runtime.subagents import Subagents
from harness.session.models import TurnEnd, UserMessageEvent
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.service import SessionService
from harness.tools import Ok, ToolContext, ToolOutcome
from harness.tools.native.subagent import (
    SubagentReply,
    SubagentStop,
    SubagentTask,
    run_subagent_tool,
)
from tests.unit.fakes import (
    EchoArgs,
    HangingClient,
    ScriptedClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    pending_tool,
)
from tests.unit.helpers import context_for, runtime_over

TASK = SubagentTask(name="aapl", task="Get AAPL revenue for four years and give the growth.")


@pytest.fixture
def sessions(tmp_path: Path) -> SessionService:
    return SessionService(JsonlSessionRepository(tmp_path))


async def test_a_subagent_answers_from_a_log_of_its_own(
    sessions: SessionService, tmp_path: Path
) -> None:
    client = ScriptedClient(completed("AAPL grew 2%."))
    subagents = Subagents(runtime_over(client, guidance="BASE"), sessions)

    outcome = await subagents("call-9.0", TASK, bot_id="b")

    assert outcome == SubagentReply(text="AAPL grew 2%.")
    assert (tmp_path / "call-9.0.jsonl").exists()
    stored = await sessions.read("call-9.0")
    assert [e.message.content for e in stored.events() if isinstance(e, UserMessageEvent)] == [
        TASK.task
    ]


async def test_a_subagent_is_told_its_name_and_keeps_the_base_prompt(
    sessions: SessionService,
) -> None:
    client = ScriptedClient(completed("done"))

    await Subagents(runtime_over(client, guidance="BASE"), sessions)("c.0", TASK, bot_id="b")

    system = client.seen[0]
    assert isinstance(system, SystemMessage)
    assert "aapl" in system.content
    assert system.content.endswith("BASE")


async def test_a_subagent_that_needs_the_person_stops_naming_the_call(
    sessions: SessionService,
) -> None:
    client = SteppedClient(calls_tool("save_note", '{"value": "x"}'))
    subagents = Subagents(runtime_over(client, pending_tool("save_note")), sessions)

    outcome = await subagents("c.0", TASK, bot_id="b")

    assert isinstance(outcome, SubagentStop)
    assert "save_note" in outcome.reason


async def test_a_subagent_whose_turn_fails_says_why(sessions: SessionService) -> None:
    client = ScriptedClient([Failed(reason="provider down")])

    outcome = await Subagents(runtime_over(client), sessions)("c.0", TASK, bot_id="b")

    assert isinstance(outcome, SubagentStop)
    assert "provider down" in outcome.reason


async def test_a_stopped_subagent_leaves_its_log_closed_as_cancelled(
    sessions: SessionService,
) -> None:
    subagents = Subagents(runtime_over(HangingClient("partial")), sessions)

    running = asyncio.create_task(subagents("c.0", TASK, bot_id="b"))
    for _ in range(50):
        await asyncio.sleep(0)
    running.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await running

    assert running.cancelled()
    stored = await sessions.read("c.0")
    assert stored.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_a_helper_runs_its_tools_for_the_bot_that_called_it(
    sessions: SessionService,
) -> None:
    seen: list[str] = []

    async def record(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        seen.append(context.origin.bot_id)
        return Ok(content=args.value)

    client = SteppedClient(calls_tool("echo", '{"value": "x"}'), completed("done"))
    helpers = Subagents(runtime_over(client, replace(echo_tool(), execute=record)), sessions)
    tasks = json.dumps({"tasks": [{"name": "aapl", "task": "Look up AAPL."}]})

    await run_subagent_tool(helpers).invoke(tasks, context=context_for("c", bot_id="notion"))

    assert seen == ["notion"]
