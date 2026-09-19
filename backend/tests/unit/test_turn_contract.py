"""What `drive` commits to: checkpoints, and the repair after a step cut short."""

from __future__ import annotations

from contextlib import aclosing

from harness.agent.events import AgentCompleted
from harness.agent.hooks import HookChain, ToolHook
from harness.agent.turn import INTERRUPTED_RESULT
from harness.llm.messages import ToolCall
from harness.llm.stream import Completed, TextChunk, ToolCallChunk
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
)
from tests.unit.fakes import (
    HangingClient,
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    hanging_tool,
    pending_tool,
)
from tests.unit.helpers import cancel_mid_turn, drain, loop_agent, new_session


class Noting(ToolHook):
    async def pre(self, sig, calls):
        return None

    async def post(self, sig, outcome, calls):
        return "careful"


def two_calls(first: ToolCall, second: ToolCall) -> list:
    return [
        ToolCallChunk(call=first),
        ToolCallChunk(call=second),
        Completed(full_text="", tool_calls=(first, second)),
    ]


async def test_a_tool_turn_checkpoints_before_each_request_and_after_each_call() -> None:
    seen: list[str] = []

    async def checkpoint(session: Session) -> None:
        seen.append(session.events()[-1].type)

    client = SteppedClient(calls_tool("echo", '{"value": "a"}'), completed("done"))
    session = new_session()

    await drain(loop_agent(client, echo_tool(), checkpoint=checkpoint).run("q", session=session))

    assert seen == ["step/start", "tool/call", "step/start"]


async def test_cancelling_mid_step_answers_only_the_calls_still_open() -> None:
    first = ToolCall(id="c1", name="echo", arguments='{"value": "a"}')
    second = ToolCall(id="c2", name="hang", arguments='{"value": "b"}')
    client = SteppedClient(two_calls(first, second))
    session = new_session()

    await cancel_mid_turn(loop_agent(client, echo_tool(), hanging_tool()), session)

    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert [(r.message.tool_call_id, r.message.text, r.error) for r in results] == [
        ("c1", "a", None),
        ("c2", INTERRUPTED_RESULT, "INTERRUPTED_BY_CRASH"),
    ]
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_cancelling_inside_the_first_call_answers_the_undispatched_second_too() -> None:
    first = ToolCall(id="c1", name="hang", arguments='{"value": "a"}')
    second = ToolCall(id="c2", name="echo", arguments='{"value": "b"}')
    client = SteppedClient(two_calls(first, second))
    session = new_session()

    await cancel_mid_turn(loop_agent(client, echo_tool(), hanging_tool()), session)

    assert [e.call.id for e in session.events() if isinstance(e, ToolCallEvent)] == ["c1"]
    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert [(r.message.tool_call_id, r.error) for r in results] == [
        ("c1", "INTERRUPTED_BY_CRASH"),
        ("c2", "INTERRUPTED_BY_CRASH"),
    ]
    assert [e.type for e in session.events()][-2:] == ["step/end", "turn/end"]


async def test_a_pending_call_then_a_cancel_in_one_step_is_a_cancel() -> None:
    first = ToolCall(id="c1", name="ask", arguments='{"value": "?"}')
    second = ToolCall(id="c2", name="hang", arguments='{"value": "b"}')
    client = SteppedClient(two_calls(first, second))
    session = new_session()

    await cancel_mid_turn(loop_agent(client, pending_tool(), hanging_tool()), session)

    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert [r.message.tool_call_id for r in results] == ["c2"]
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_a_note_gathered_before_a_cancel_is_dropped() -> None:
    first = ToolCall(id="c1", name="echo", arguments='{"value": "a"}')
    second = ToolCall(id="c2", name="hang", arguments='{"value": "b"}')
    client = SteppedClient(two_calls(first, second))
    session = new_session()
    agent_ = loop_agent(client, echo_tool(), hanging_tool(), hooks=HookChain((Noting(),)))

    await cancel_mid_turn(agent_, session)

    assert not any(isinstance(e, ApplicationMessageEvent) for e in session.events())


async def test_a_note_is_logged_before_a_pending_turn_ends() -> None:
    first = ToolCall(id="c1", name="echo", arguments='{"value": "a"}')
    second = ToolCall(id="c2", name="ask", arguments='{"value": "?"}')
    client = SteppedClient(two_calls(first, second))
    session = new_session()
    agent_ = loop_agent(client, echo_tool(), pending_tool(), hooks=HookChain((Noting(),)))

    await drain(agent_.run("q", session=session))

    assert [e.type for e in session.events()][-4:] == [
        "tool/call",
        "application/message",
        "step/end",
        "turn/end",
    ]
    assert session.events()[-1] == TurnEnd(turn=0, reason="pending")


async def test_closing_at_the_terminal_does_not_close_the_turn_twice() -> None:
    session = new_session()

    async with aclosing(
        loop_agent(SteppedClient(completed("ok"))).run("q", session=session)
    ) as events:
        async for event in events:
            if isinstance(event, AgentCompleted):
                break

    assert [e for e in session.events() if isinstance(e, TurnEnd)] == [
        TurnEnd(turn=0, reason="completed")
    ]


async def test_an_interrupted_second_step_is_stamped_with_its_own_step() -> None:
    class HangsOnStepOne(HangingClient):
        def __init__(self) -> None:
            super().__init__("partial")
            self.calls = 0

        async def stream_completion(self, messages, model, *, tools=None):
            self.calls += 1
            if self.calls == 1:
                for event in calls_tool("echo", '{"value": "a"}'):
                    yield event
                return
            async with aclosing(super().stream_completion(messages, model, tools=tools)) as s:
                async for event in s:
                    yield event

    client = HangsOnStepOne()
    session = new_session()

    async with aclosing(loop_agent(client, echo_tool()).run("q", session=session)) as events:
        async for event in events:
            if isinstance(event, TextChunk):
                break

    messages = [e for e in session.events() if isinstance(e, AssistantMessageEvent)]
    assert [(m.step, m.interrupted, m.message.content) for m in messages] == [
        (0, False, ""),
        (1, True, "partial"),
    ]
    assert not any(isinstance(e, ToolResultEvent) and e.error for e in session.events())
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")
