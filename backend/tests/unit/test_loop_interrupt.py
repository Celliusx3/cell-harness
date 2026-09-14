"""Interrupting a turn: every dispatched call still gets a result.

A provider rejects a history with an unanswered call outright, so an abandoned
turn must answer everything it asked for — and the assertion the other tests
lean on to prove that is itself tested here.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import aclosing

from harness.agent.loop import INTERRUPTED_RESULT
from harness.llm.messages import AssistantMessage, ToolCall, ToolMessage, UserMessage
from harness.llm.stream import ToolCallChunk
from harness.session.derive import derive_messages
from harness.session.log import Session
from harness.session.models import ToolCallEvent, ToolResultEvent, TurnEnd
from tests.unit.fakes import SteppedClient, calls_tool, echo_tool, hanging_tool
from tests.unit.helpers import loop_agent, new_session, unanswered_calls


async def interrupt_during_tool(agent_, session: Session) -> None:
    """Cancel a turn while a dispatched tool is still running.

    Cancelling the consuming task is what a closed browser tab does. It has to be
    a task rather than a `break`, because the consumer is *blocked* inside the
    tool call — there is no next event to break on.
    """

    async def consume() -> None:
        async with aclosing(agent_.run("q", session=session)) as events:
            async for _ in events:
                pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let it reach the hanging tool
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_every_dispatched_call_gets_a_result_even_when_interrupted() -> None:
    """A provider rejects a history with an unanswered call outright, so an
    abandoned turn must still answer everything it asked for."""
    client = SteppedClient(calls_tool("hang", '{"value": "a"}'))
    session = new_session()

    await interrupt_during_tool(loop_agent(client, hanging_tool()), session)

    calls = [e for e in session.events() if isinstance(e, ToolCallEvent)]
    results = [e for e in session.events() if isinstance(e, ToolResultEvent)]
    assert len(calls) == 1
    assert len(results) == len(calls)
    assert unanswered_calls(derive_messages(session.events())) == []
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_an_interrupted_call_records_a_recoverable_error() -> None:
    client = SteppedClient(calls_tool("hang", '{"value": "a"}'))
    session = new_session()

    await interrupt_during_tool(loop_agent(client, hanging_tool()), session)

    result = next(e for e in session.events() if isinstance(e, ToolResultEvent))
    assert result.message.text == INTERRUPTED_RESULT
    assert result.error == "INTERRUPTED_BY_CRASH"


async def test_stopping_before_any_call_exists_owes_nothing() -> None:
    """Interrupting during the model stream is not the repair path: no call has
    been made, so there is nothing to answer."""
    client = SteppedClient(calls_tool("echo", '{"value": "a"}'))
    session = new_session()

    async with aclosing(loop_agent(client, echo_tool()).run("q", session=session)) as events:
        async for event in events:
            if isinstance(event, ToolCallChunk):
                break

    assert not any(isinstance(e, ToolCallEvent) for e in session.events())
    assert not any(isinstance(e, ToolResultEvent) for e in session.events())
    assert unanswered_calls(derive_messages(session.events())) == []


def test_the_unanswered_calls_assertion_actually_detects_a_gap() -> None:
    """The other tests lean on this to prove the repair path worked, so an
    assertion that silently reports everything as fine would hide the bug it
    exists to catch."""
    asked = AssistantMessage(
        content="checking",
        tool_calls=(
            ToolCall(id="c1", name="echo", arguments="{}"),
            ToolCall(id="c2", name="echo", arguments="{}"),
        ),
    )
    half = [UserMessage(content="q"), asked, ToolMessage(tool_call_id="c1", content="ok")]

    assert unanswered_calls([UserMessage(content="q")]) == []
    assert unanswered_calls(half) == ["c2"]
    assert unanswered_calls([*half, ToolMessage(tool_call_id="c2", content="ok")]) == []
