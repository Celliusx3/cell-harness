"""A chat's mode: the latest switch wins, Auto runs what Ask holds, and questions still wait."""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.llm import ToolCall, text_of
from harness.sandbox import Bridge, BridgeError
from harness.session.domain.models import ApprovalModeChanged, ChatCleared, ToolResultEvent, TurnEnd
from harness.tools import (
    ApprovalMode,
    ApprovalService,
    CallOrigin,
    Ok,
    Pending,
    ToolContext,
    ToolService,
)
from harness.tools.native.code_mode import EXECUTE_TYPESCRIPT
from harness.tools.native.location import GET_LOCATION
from harness.tools.native.question import ASK_USER
from tests.unit.code_fakes import FakeRunner, build, tool
from tests.unit.fakes import SteppedClient, calls_tool, completed, echo_tool, gated_tool
from tests.unit.helpers import (
    client_tools,
    durable_service,
    new_session,
    no_progress,
    run_service,
    toolset_for,
    until,
)

WRITE = "memory__write_note"


def _approvals(*protected: str, default_mode: ApprovalMode = "ask") -> ApprovalService:
    return ApprovalService(
        frozenset(protected),
        frozenset,
        Path("/nonexistent/approvals.json"),
        default_mode=default_mode,
    )


def _origin(mode: ApprovalMode) -> CallOrigin:
    return CallOrigin(bot_id="s", conversation_id="s", mode=mode)


def test_a_chat_with_no_switch_follows_the_default() -> None:
    assert new_session().approval_mode("ask") == "ask"
    assert new_session().approval_mode("auto") == "auto"


def test_the_latest_switch_wins() -> None:
    session = new_session()
    session.append(ApprovalModeChanged(mode="auto"))
    session.append(ChatCleared())
    session.append(ApprovalModeChanged(mode="ask"))

    assert session.approval_mode("auto") == "ask"


async def test_auto_runs_a_call_that_ask_holds() -> None:
    tools = ToolService([echo_tool(WRITE)], approvals=_approvals(WRITE))
    call = ToolCall(id="c1", name=WRITE, arguments='{"value": "hi"}')

    held = await tools.dispatch(call, progress=no_progress, approved=False, origin=_origin("ask"))
    ran = await tools.dispatch(call, progress=no_progress, approved=False, origin=_origin("auto"))

    assert held == Pending()
    assert ran == Ok(content="hi")


async def test_a_question_to_the_person_still_waits_in_auto() -> None:
    tools = ToolService(client_tools().tools(), approvals=_approvals())
    location = ToolCall(id="c1", name=GET_LOCATION, arguments="{}")
    question = ToolCall(
        id="c2",
        name=ASK_USER,
        arguments='{"question": "Tea?", "options": ["Yes", "No"]}',
    )

    outcomes = [
        await tools.dispatch(call, progress=no_progress, approved=False, origin=_origin("auto"))
        for call in (location, question)
    ]

    assert outcomes == [Pending(), Pending()]


def test_a_chat_runs_under_its_latest_switch_else_the_configured_default() -> None:
    toolset = toolset_for(approvals=_approvals(default_mode="auto"))
    session = new_session()

    assert toolset.approval_mode(session) == "auto"
    session.append(ApprovalModeChanged(mode="ask"))
    assert toolset.approval_mode(session) == "ask"


async def _script_calls_write(mode: ApprovalMode) -> list[BridgeError]:
    raised: list[BridgeError] = []

    async def script(bridge: Bridge) -> None:
        try:
            await bridge(WRITE, {})
        except BridgeError as err:
            raised.append(err)

    built = build(tool(WRITE), runner=FakeRunner(script=script), approvals=_approvals(WRITE))
    context = ToolContext(call_id="c1", progress=no_progress, origin=_origin(mode))
    await built.tool(EXECUTE_TYPESCRIPT).invoke(
        '{"code": "…", "description": "d"}', context=context
    )
    return raised


async def test_a_script_follows_the_chat_mode() -> None:
    asked = await _script_calls_write("ask")
    auto = await _script_calls_write("auto")

    assert "waits for the user's approval" in str(asked[0])
    assert auto == []


async def test_a_switch_during_a_turn_decides_its_next_call(tmp_path) -> None:
    release = asyncio.Event()
    service = durable_service(tmp_path / "sessions")
    runs = run_service(
        service,
        SteppedClient(
            calls_tool("gate", '{"value": "wait"}', id="c1"),
            calls_tool(WRITE, '{"value": "Kopi"}', id="c2"),
            completed("done"),
        ),
        gated_tool(release),
        echo_tool(WRITE),
        approvals=_approvals(WRITE),
    )
    run = runs.start(await service.create(ASSISTANT_ID), "go")
    await until(lambda: runs.active(ASSISTANT_ID) is not None, what="the turn to start")

    await runs.set_approval_mode(ASSISTANT_ID, "auto")
    release.set()
    await asyncio.wait_for(run._outer, timeout=5)

    events = (await service.read(ASSISTANT_ID)).events()
    assert ApprovalModeChanged(mode="auto") in events
    written = [
        text_of(e.message.content)
        for e in events
        if isinstance(e, ToolResultEvent) and e.message.tool_call_id == "c2"
    ]
    assert written == ["Kopi"]
    assert [e.reason for e in events if isinstance(e, TurnEnd)] == ["completed"]
