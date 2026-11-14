"""A tool whose result ends the turn: nothing after its step runs."""

from __future__ import annotations

from harness.llm import Completion, ToolCall, ToolCallChunk
from harness.runtime.events import AgentCompleted
from harness.session.domain.models import ToolResultEvent, TurnEnd
from harness.tools import BLOCKED, Ok, Tool, ToolContext, ToolOutcome
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool
from tests.unit.helpers import drain, new_session, runtime_over


def final_tool() -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        return Ok(content=args.value, ends_turn=True)

    return Tool.from_model(
        name="final", description="Say the last thing.", args_model=EchoArgs, execute=execute
    )


async def test_a_result_that_ends_the_turn_stops_the_turn_after_its_step() -> None:
    client = SteppedClient(
        calls_tool("final", '{"value": "reported"}', id="c1"),
        calls_tool("final", '{"value": "again"}', id="c2"),
    )
    session = new_session()

    events = await drain(runtime_over(client, final_tool()).run("go", session=session, bot_id="b"))

    assert client.calls == 1
    assert session.events()[-1] == TurnEnd(turn=0, reason="completed")
    assert isinstance(events[-1], AgentCompleted)


async def test_a_call_listed_after_one_that_ends_the_turn_does_not_run() -> None:
    echoed: list[str] = []
    final = ToolCall(id="c1", name="final", arguments='{"value": "reported"}')
    after = ToolCall(id="c2", name="echo", arguments='{"value": "late"}')
    client = SteppedClient(
        [
            ToolCallChunk(call=final),
            ToolCallChunk(call=after),
            Completion(full_text="", tool_calls=(final, after)),
        ]
    )
    session = new_session()

    await drain(
        runtime_over(client, final_tool(), recording_tool(echoed)).run(
            "go", session=session, bot_id="b"
        )
    )

    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert echoed == []
    assert [r.error for r in results] == [None, BLOCKED]
    assert session.events()[-1] == TurnEnd(turn=0, reason="completed")


def recording_tool(seen: list[str]) -> Tool[EchoArgs]:
    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        seen.append(args.value)
        return Ok(content=args.value)

    return Tool.from_model(
        name="echo", description="Echo the value back.", args_model=EchoArgs, execute=execute
    )
