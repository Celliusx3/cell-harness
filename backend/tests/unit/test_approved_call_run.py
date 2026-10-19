"""An approved call runs like any other: reported as it goes, noted after, closed if cancelled."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import aclosing

from harness.runtime.events import ToolProgress, ToolResult
from harness.runtime.hooks import HookChain, ToolHook
from harness.session.models import ApplicationMessageEvent, ToolResultEvent, TurnEnd
from harness.session.repair import REPAIRED
from harness.tools import Approval, Ok, Tool, ToolOutcome
from tests.unit.approval_fakes import WRITE, approvals_asking_for, note_writer, runtime_offering
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed, reporting_tool
from tests.unit.helpers import drain, new_session


async def test_cancel_during_an_approved_run_closes_the_turn(tmp_path) -> None:
    started = asyncio.Event()

    async def execute(_args: EchoArgs, _context) -> ToolOutcome:
        started.set()
        await asyncio.sleep(60)
        return Ok(content="never")

    slow = Tool.from_model(name=WRITE, description="d", args_model=EchoArgs, execute=execute)
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("never"))
    session = new_session()
    runtime = runtime_offering(client, approvals_asking_for(tmp_path, WRITE), slow)
    await drain(runtime.run("remember Kopi", session=session, bot_id="b"))

    async def consume() -> None:
        async with aclosing(
            runtime.resume("c1", Approval(scope="once"), session=session, bot_id="b")
        ) as events:
            async for _ in events:
                pass

    task = asyncio.create_task(consume())
    await started.wait()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.message.tool_call_id == "c1" and result.error == REPAIRED
    assert session.events()[-1] == TurnEnd(turn=1, reason="cancelled")
    assert client.calls == 1


async def test_an_approved_calls_progress_reaches_the_caller_before_its_result(tmp_path) -> None:
    client = SteppedClient(calls_tool("slow", '{"value": "done"}', id="c1"), completed("ok"))
    session = new_session()
    runtime = runtime_offering(
        client, approvals_asking_for(tmp_path, "slow"), reporting_tool([(50.0, "halfway")])
    )
    await drain(runtime.run("go", session=session, bot_id="b"))

    events = await drain(runtime.resume("c1", Approval(scope="once"), session=session, bot_id="b"))

    progress, result = events[0], events[1]
    assert isinstance(progress, ToolProgress) and progress.message == "halfway"
    assert isinstance(result, ToolResult) and result.tool_call_id == "c1"


async def test_an_approved_calls_note_is_logged_after_its_result(tmp_path) -> None:
    class Noting(ToolHook):
        async def pre(self, sig, prior) -> str | None:
            return None

        async def post(self, sig, outcome, prior) -> str | None:
            return "careful"

    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("saved"))
    session = new_session()
    runtime = runtime_offering(
        client, approvals_asking_for(tmp_path, WRITE), note_writer([]), hooks=HookChain((Noting(),))
    )
    await drain(runtime.run("remember Kopi", session=session, bot_id="b"))

    await drain(runtime.resume("c1", Approval(scope="once"), session=session, bot_id="b"))

    kinds = [e.type for e in session.events() if e.type in ("tool/result", "application/message")]
    assert kinds == ["tool/result", "application/message"]
    note = next(e for e in session.events() if isinstance(e, ApplicationMessageEvent))
    assert note.message.content == "careful" and note.turn == 1
