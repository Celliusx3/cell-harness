"""A listed tool asks the person before it runs; their answer opens the next turn."""

from __future__ import annotations

import dataclasses

from harness.llm import Completed, ToolCall, ToolCallChunk, ToolMessage
from harness.runtime.events import AgentCompleted, AgentPending
from harness.runtime.hooks import HookChain, ToolHook
from harness.sandbox import Bridge, BridgeError
from harness.session.models import (
    ApprovalGrant,
    ToolResultEvent,
    TurnEnd,
)
from harness.tools import (
    BLOCKED,
    REFUSED,
    Approval,
    Failure,
    Ok,
    Toolset,
)
from harness.tools.client import AcceptedAnswer, ClientTools, ClientToolService
from harness.tools.models.decision import DENIED
from tests.unit.approval_fakes import WRITE, approvals_asking_for, note_writer, runtime_offering
from tests.unit.code_fakes import FakeRunner, build, tool
from tests.unit.fakes import SteppedClient, calls_tool, completed
from tests.unit.helpers import drain, new_session


def _step_with(*calls: ToolCall) -> list:
    return [*(ToolCallChunk(call=c) for c in calls), Completed(full_text="", tool_calls=calls)]


async def test_a_listed_tool_ends_the_turn_pending_and_does_not_run(tmp_path) -> None:
    ran: list[str] = []
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("never"))
    session = new_session()

    events = await drain(
        runtime_offering(client, approvals_asking_for(tmp_path, WRITE), note_writer(ran)).run(
            "remember Kopi", session=session, bot_id="b"
        )
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
    runtime = runtime_offering(client, approvals_asking_for(tmp_path, WRITE), note_writer(ran))
    await drain(runtime.run("remember Kopi", session=session, bot_id="b"))

    events = await drain(runtime.resume("c1", Approval(scope="once"), session=session, bot_id="b"))

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
    runtime = runtime_offering(client, approvals_asking_for(tmp_path, WRITE), note_writer(ran))
    await drain(runtime.run("remember Kopi", session=session, bot_id="b"))
    service = ClientToolService(ClientTools(()), approvals_asking_for(tmp_path, WRITE))
    accepted = service.accept_by_call_id(session, "c1", {"kind": "denied"})
    assert isinstance(accepted, AcceptedAnswer) and isinstance(accepted.outcome, Failure)
    assert accepted.outcome.code == DENIED

    await drain(runtime.resume("c1", accepted.outcome, session=session, bot_id="b"))

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
    runtime = runtime_offering(client, approvals_asking_for(tmp_path, WRITE), note_writer(ran))
    await drain(runtime.run("remember Kopi", session=session, bot_id="b"))

    await drain(runtime.resume("c1", Approval(scope="conversation"), session=session, bot_id="b"))
    events = await drain(runtime.run("and Teh", session=session, bot_id="b"))

    assert ran == ["Kopi", "Teh"]
    grants = [e for e in session.events() if isinstance(e, ApprovalGrant)]
    assert grants == [ApprovalGrant(turn=1, tool=WRITE)]
    assert session.conversation_approved_tools() == frozenset({WRITE})
    assert events[-1] == AgentCompleted(text="saved again")
    assert [e.reason for e in session.events() if isinstance(e, TurnEnd)] == [
        "pending",
        "completed",
        "completed",
    ]


async def test_a_tool_allowed_for_the_conversation_is_refused_once_it_is_not_offered(
    tmp_path,
) -> None:
    ran: list[str] = []
    session = new_session()
    first = runtime_offering(
        SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("saved")),
        approvals_asking_for(tmp_path, WRITE),
        note_writer(ran),
    )
    await drain(first.run("remember Kopi", session=session, bot_id="b"))
    await drain(first.resume("c1", Approval(scope="conversation"), session=session, bot_id="b"))
    assert first.tools is not None
    later = dataclasses.replace(
        first,
        client=SteppedClient(calls_tool(WRITE, '{"value": "Teh"}', id="c2"), completed("ok")),
        tools=Toolset(first.tools.tool_service, default_tools=[]),
    )

    await drain(later.run("and Teh", session=session, bot_id="b"))

    assert ran == ["Kopi"]
    second = [e for e in session.events() if isinstance(e, ToolResultEvent)][-1]
    assert second.message.tool_call_id == "c2" and second.error == REFUSED


async def test_a_second_listed_call_keeps_the_turn_pending_until_it_is_answered(tmp_path) -> None:
    ran: list[str] = []
    calls = (
        ToolCall(id="c1", name=WRITE, arguments='{"value": "Kopi"}'),
        ToolCall(id="c2", name=WRITE, arguments='{"value": "Teh"}'),
    )
    client = SteppedClient(_step_with(*calls), completed("both saved"))
    session = new_session()
    approvals = approvals_asking_for(tmp_path, WRITE)
    runtime = runtime_offering(client, approvals, note_writer(ran))
    service = ClientToolService(ClientTools(()), approvals)
    await drain(runtime.run("remember both", session=session, bot_id="b"))
    assert {p.call_id for p in service.answerable_calls(session)} == {"c1", "c2"}

    first = await drain(runtime.resume("c1", Approval(scope="once"), session=session, bot_id="b"))

    assert ran == ["Kopi"]
    assert first[-1] == AgentPending(tool_call_id="c2", name=WRITE)
    assert session.events()[-1] == TurnEnd(turn=1, reason="pending")
    assert [p.call_id for p in service.answerable_calls(session)] == ["c2"]
    assert client.calls == 1

    second = await drain(runtime.resume("c2", Approval(scope="once"), session=session, bot_id="b"))

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

    built = build(
        tool(WRITE),
        runner=FakeRunner(script=script),
        approvals=approvals_asking_for(tmp_path, WRITE),
    )

    listed = await built.run("list_functions", "{}")
    assert isinstance(listed, Ok) and WRITE in listed.text
    await built.run("execute_typescript", '{"code": "…", "description": "d"}')
    assert "approval" in str(raised[0]) and "get_function_details" in str(raised[0])


async def test_a_hook_refusal_never_reaches_the_approvals(tmp_path) -> None:
    class Refuse(ToolHook):
        async def pre(self, sig, prior) -> str | None:
            return "no"

        async def post(self, sig, outcome, prior) -> str | None:
            return None

    ran: list[str] = []
    client = SteppedClient(calls_tool(WRITE, '{"value": "Kopi"}', id="c1"), completed("ok"))
    session = new_session()
    runtime = runtime_offering(
        client,
        approvals_asking_for(tmp_path, WRITE),
        note_writer(ran),
        hooks=HookChain((Refuse(),)),
    )

    events = await drain(runtime.run("remember Kopi", session=session, bot_id="b"))

    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.error == BLOCKED
    assert events[-1] == AgentCompleted(text="ok")
