"""A listed tool asks the person before it runs; their answer opens the next turn."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import aclosing
from pathlib import Path

from harness.agent.events import AgentCompleted, AgentPending
from harness.agent.hooks import HookChain, ToolHook
from harness.agent.loop import LoopAgent
from harness.llm.messages import ToolCall, ToolMessage
from harness.llm.stream import Completed, ToolCallChunk
from harness.sandbox import Bridge, BridgeError
from harness.session.models import ApprovalGrant, ToolResultEvent, TurnEnd
from harness.session.repair import REPAIRED
from harness.tools.approval import DENIED, ApprovalGate, Approved
from harness.tools.client import Accepted, ClientTools, ClientToolService
from harness.tools.definition import BLOCKED, Failure, Ok, ToolDefinition, ToolOutcome
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.pipeline import ToolPipeline
from harness.tools.registry import ToolRegistry
from tests.unit.code_fakes import FakeRunner, build, tool
from tests.unit.fakes import EchoArgs, SteppedClient, calls_tool, completed
from tests.unit.helpers import drain, new_session

WRITE = "memory__write_note"


def _gate(tmp_path: Path, *tools: str) -> ApprovalGate:
    return ApprovalGate(frozenset(tools), tmp_path / "approvals.json")


def _writer(ran: list[str]) -> ToolDefinition[EchoArgs]:
    async def execute(args: EchoArgs, _context) -> ToolOutcome:
        ran.append(args.value)
        return Ok(content=f"saved {args.value}")

    return ToolDefinition.from_model(
        name=WRITE, description="Save a note.", args_model=EchoArgs, execute=execute
    )


def _agent(
    client, gate: ApprovalGate, *tools: ToolDefinition, hooks: HookChain | None = None
) -> LoopAgent:
    registry = ToolRegistry(tools)
    pipeline = ToolPipeline(
        registry, ToolDispatcher(registry, gate), default_tools=[t.name for t in tools]
    )
    return LoopAgent(name="t", model="m", client=client, tools=pipeline, hooks=hooks or HookChain())


def _types(session) -> list[str]:
    return [e.type for e in session.events()]


def _step_with(*calls: ToolCall) -> list:
    return [*(ToolCallChunk(call=c) for c in calls), Completed(full_text="", tool_calls=calls)]


async def test_a_listed_tool_ends_the_turn_pending_and_does_not_run(tmp_path) -> None:
    ran: list[str] = []
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("never"))
    session = new_session()

    events = await drain(
        _agent(client, _gate(tmp_path, WRITE), _writer(ran)).run("remember Kopi", session=session)
    )

    assert ran == []
    assert session.events()[-1] == TurnEnd(turn=0, reason="pending")
    assert not any(isinstance(e, ToolResultEvent) for e in session.events())
    assert events[-1] == AgentPending(tool_call_id="c1", name=WRITE)


async def test_allow_once_runs_the_call_in_the_next_turn_and_the_model_sees_its_result(
    tmp_path,
) -> None:
    ran: list[str] = []
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("saved"))
    session = new_session()
    agent = _agent(client, _gate(tmp_path, WRITE), _writer(ran))
    await drain(agent.run("remember Kopi", session=session))

    events = await drain(agent.resume("c1", Approved(scope="once"), session=session))

    assert ran == ["Kopi"]
    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.error is None and result.turn == 1
    assert events[-1] == AgentCompleted(text="saved")
    seen = client.seen_per_call[-1]
    assert seen[-2].tool_calls[0].id == "c1"
    assert seen[-1] == ToolMessage(tool_call_id="c1", content=Ok(content="saved Kopi").content)


async def test_deny_writes_a_denied_result_the_model_reads(tmp_path) -> None:
    ran: list[str] = []
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("not saved"))
    session = new_session()
    agent = _agent(client, _gate(tmp_path, WRITE), _writer(ran))
    await drain(agent.run("remember Kopi", session=session))
    service = ClientToolService(ClientTools(()), _gate(tmp_path, WRITE))
    accepted = service.accept_call(session, "c1", {"kind": "denied"})
    assert isinstance(accepted, Accepted) and isinstance(accepted.outcome, Failure)
    assert accepted.outcome.code == DENIED

    await drain(agent.resume("c1", accepted.outcome, session=session))

    assert ran == []
    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.error == DENIED
    assert "did not run" in result.message.content[0].text
    assert "do not retry" in result.message.content[0].text.lower()


async def test_allow_for_the_conversation_writes_a_grant_and_the_next_call_runs_unasked(
    tmp_path,
) -> None:
    ran: list[str] = []
    client = SteppedClient(
        calls_tool(WRITE, '{"value": "Kopi"}', id="c1"),
        completed("saved"),
        calls_tool(WRITE, '{"value": "Teh"}', id="c2"),
        completed("saved again"),
    )
    session = new_session()
    agent = _agent(client, _gate(tmp_path, WRITE), _writer(ran))
    await drain(agent.run("remember Kopi", session=session))

    await drain(agent.resume("c1", Approved(scope="conversation"), session=session))
    events = await drain(agent.run("and Teh", session=session))

    assert ran == ["Kopi", "Teh"]
    grants = [e for e in session.events() if isinstance(e, ApprovalGrant)]
    assert grants == [ApprovalGrant(turn=1, tool=WRITE)]
    assert session.tools_granted() == frozenset({WRITE})
    assert events[-1] == AgentCompleted(text="saved again")
    assert [e.reason for e in session.events() if isinstance(e, TurnEnd)] == [
        "pending",
        "completed",
        "completed",
    ]


async def test_a_second_listed_call_keeps_the_turn_pending_until_it_is_answered(tmp_path) -> None:
    ran: list[str] = []
    calls = (
        ToolCall(id="c1", name=WRITE, arguments='{"value": "Kopi"}'),
        ToolCall(id="c2", name=WRITE, arguments='{"value": "Teh"}'),
    )
    client = SteppedClient(_step_with(*calls), completed("both saved"))
    session = new_session()
    gate = _gate(tmp_path, WRITE)
    agent = _agent(client, gate, _writer(ran))
    service = ClientToolService(ClientTools(()), gate)
    await drain(agent.run("remember both", session=session))
    assert {p.call_id for p in service.pending(session)} == {"c1", "c2"}

    first = await drain(agent.resume("c1", Approved(scope="once"), session=session))

    assert ran == ["Kopi"]
    assert first[-1] == AgentPending(tool_call_id="c2", name=WRITE)
    assert session.events()[-1] == TurnEnd(turn=1, reason="pending")
    assert [p.call_id for p in service.pending(session)] == ["c2"]
    assert client.calls == 1

    second = await drain(agent.resume("c2", Approved(scope="once"), session=session))

    assert ran == ["Kopi", "Teh"]
    assert second[-1] == AgentCompleted(text="both saved")
    assert client.calls == 2


async def test_a_script_calling_a_listed_tool_is_refused_and_told_to_call_it_directly(
    tmp_path,
) -> None:
    raised: list[BridgeError] = []

    async def script(bridge: Bridge) -> None:
        try:
            await bridge(WRITE, {"value": "Kopi"})
        except BridgeError as err:
            raised.append(err)

    built = build(tool(WRITE), runtime=FakeRunner(script=script), gate=_gate(tmp_path, WRITE))

    listed = await built.run("list_functions", "{}")
    assert isinstance(listed, Ok) and WRITE in listed.text
    await built.run("execute_typescript", '{"code": "…", "description": "d"}')
    assert "approval" in str(raised[0]) and "get_function_details" in str(raised[0])


async def test_cancel_during_an_approved_run_closes_the_turn(tmp_path) -> None:
    started = asyncio.Event()

    async def execute(_args: EchoArgs, _context) -> ToolOutcome:
        started.set()
        await asyncio.sleep(60)
        return Ok(content="never")

    slow = ToolDefinition.from_model(
        name=WRITE, description="d", args_model=EchoArgs, execute=execute
    )
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("never"))
    session = new_session()
    agent = _agent(client, _gate(tmp_path, WRITE), slow)
    await drain(agent.run("remember Kopi", session=session))

    async def consume() -> None:
        async with aclosing(agent.resume("c1", Approved(scope="once"), session=session)) as events:
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


async def test_a_hook_refusal_never_reaches_the_gate(tmp_path) -> None:
    class Refuse(ToolHook):
        async def pre(self, sig, prior) -> str | None:
            return "no"

        async def post(self, sig, outcome, prior) -> str | None:
            return None

    ran: list[str] = []
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("ok"))
    session = new_session()
    agent = _agent(client, _gate(tmp_path, WRITE), _writer(ran), hooks=HookChain((Refuse(),)))

    events = await drain(agent.run("remember Kopi", session=session))

    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.error == BLOCKED
    assert events[-1] == AgentCompleted(text="ok")
