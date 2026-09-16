"""A turn that ends because the person must answer, and the turn that answers it.

A client tool does not compute: its outcome is `Pending`, and the loop ends
the turn there with no result for the call. Later, `resume` opens a new turn
with that result; or `run` opens one with a user message and first answers
the dangling call as skipped — a provider refuses a history with a call and
no result, so that line is not optional.
"""

from __future__ import annotations

from harness.agent.events import AgentCompleted, AgentPending
from harness.agent.loop import SKIPPED
from harness.llm.messages import AssistantMessage, ToolCall, ToolMessage
from harness.llm.stream import Completed, ToolCallChunk
from harness.session.models import ToolResultEvent, TurnEnd
from harness.tools.definition import Ok
from tests.unit.fakes import (
    SteppedClient,
    calls_tool,
    completed,
    echo_tool,
    pending_tool,
)
from tests.unit.helpers import drain, loop_agent, new_session


def _types(session) -> list[str]:
    return [e.type for e in session.events()]


async def test_a_pending_tool_ends_the_turn_without_a_result() -> None:
    client = SteppedClient(calls_tool("ask", '{"value": "?"}', id="c1"), completed("never"))
    session = new_session()

    events = await drain(loop_agent(client, pending_tool()).run("near me?", session=session))

    assert _types(session)[-4:] == ["assistant/message", "tool/call", "step/end", "turn/end"]
    assert session.events()[-1] == TurnEnd(turn=0, reason="pending")
    assert not any(isinstance(e, ToolResultEvent) for e in session.events())
    assert [type(e).__name__ for e in events[-2:]] == ["ToolPending", "AgentPending"]
    assert events[-1] == AgentPending(tool_call_id="c1", name="ask")
    assert client.calls == 1  # the model was not asked again


async def test_a_parallel_ordinary_call_still_gets_its_result() -> None:
    """The model may ask for a location and a clock in one step. Only the
    client's call is left open; the other is answered and logged as ever."""
    calls = (
        ToolCall(id="c1", name="echo", arguments='{"value": "42"}'),
        ToolCall(id="c2", name="ask", arguments='{"value": "?"}'),
    )
    script = [*(ToolCallChunk(call=c) for c in calls), Completed(full_text="", tool_calls=calls)]
    client = SteppedClient(script, completed("never"))
    session = new_session()

    events = await drain(loop_agent(client, echo_tool(), pending_tool()).run("q", session=session))

    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert [r.message.tool_call_id for r in results] == ["c1"]
    settled = [
        type(e).__name__
        for e in events
        if type(e).__name__ in ("ToolResult", "ToolPending", "AgentPending")
    ]
    assert settled == ["ToolResult", "ToolPending", "AgentPending"]
    assert session.events()[-1] == TurnEnd(turn=0, reason="pending")


async def test_resume_opens_a_turn_with_the_result_and_the_model_sees_it_in_order() -> None:
    client = SteppedClient(calls_tool("ask", '{"value": "?"}', id="c1"), completed("cafés nearby"))
    session = new_session()
    agent = loop_agent(client, pending_tool())
    await drain(agent.run("near me?", session=session))

    events = await drain(agent.resume("c1", Ok(content='{"lat": 3.1}'), session=session))

    types = _types(session)
    opened = types.index("turn/start", 1)
    assert types[opened - 1 : opened + 3] == ["turn/end", "turn/start", "tool/result", "step/start"]
    assert types[-3:] == ["assistant/message", "step/end", "turn/end"]
    assert session.events()[-1] == TurnEnd(turn=1, reason="completed")
    assert events[-1] == AgentCompleted(text="cafés nearby")
    # The wire: the assistant's request, then its result, then nothing else new.
    seen = client.seen_per_call[-1]
    assert isinstance(seen[-2], AssistantMessage) and seen[-2].tool_calls[0].id == "c1"
    assert seen[-1] == ToolMessage(tool_call_id="c1", content=Ok(content='{"lat": 3.1}').content)


async def test_a_new_message_first_answers_the_dangling_call_as_skipped() -> None:
    client = SteppedClient(
        calls_tool("ask", '{"value": "?"}', id="c1"), completed("it is 9pm in Tokyo")
    )
    session = new_session()
    agent = loop_agent(client, pending_tool())
    await drain(agent.run("near me?", session=session))

    await drain(agent.run("never mind, time in Tokyo?", session=session))

    skipped = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert skipped.error == SKIPPED
    assert skipped.message.tool_call_id == "c1"
    assert skipped.turn == 0  # stamped with the call it answers, not the new turn
    types = _types(session)
    assert types[types.index("tool/result") + 1 :][:2] == ["turn/start", "user/message"]
    seen = client.seen_per_call[-1]
    assert [type(m).__name__ for m in seen[-3:]] == [
        "AssistantMessage",
        "ToolMessage",
        "UserMessage",
    ]
    assert "continued without answering" in seen[-2].content[0].text  # type: ignore[union-attr]


async def test_an_ordinary_turn_writes_no_skips() -> None:
    client = SteppedClient(calls_tool("echo", '{"value": "42"}'), completed("done"))
    session = new_session()
    agent = loop_agent(client, echo_tool())
    await drain(agent.run("q", session=session))
    await drain(agent.run("again", session=session))

    assert [e.error for e in session.events() if isinstance(e, ToolResultEvent)] == [None]
