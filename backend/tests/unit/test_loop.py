"""The turn loop — phase 1's acceptance criteria."""

from __future__ import annotations

import asyncio
from contextlib import aclosing

import pytest

from harness.agent.events import AgentCompleted, AgentFailed
from harness.agent.loop import LoopAgent
from harness.agent.turn import NO_TERMINAL
from harness.llm.messages import SystemMessage
from harness.llm.stream import Completed, Failed, TextChunk
from harness.session.models import (
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.fakes import HangingClient, ScriptedClient, completed
from tests.unit.helpers import new_session


def agent(client, *, system_prompt: str = "") -> LoopAgent:
    return LoopAgent(name="t", model="m", client=client, system_prompt=system_prompt)


async def drain(gen) -> list:
    return [event async for event in gen]


async def test_streams_a_reply_and_records_the_turn() -> None:
    client = ScriptedClient(completed("hello"))
    session = new_session()

    events = await drain(agent(client).run("hi", session=session))

    assert events == [TextChunk(text="hello"), AgentCompleted(text="hello")]
    types = [type(e) for e in session.events()]
    assert types == [
        TurnStart,
        UserMessageEvent,
        StepStart,
        AssistantChunk,
        AssistantChunk,
        AssistantMessageEvent,
        StepEnd,
        TurnEnd,
    ]
    assert session.events()[-1].reason == "completed"


async def test_history_comes_from_the_log_not_an_accumulated_list() -> None:
    client = ScriptedClient(completed("one"))
    session = new_session()

    await drain(agent(client).run("first", session=session))
    client._script = completed("two")
    await drain(agent(client).run("second", session=session))

    assert [(m.role, m.content) for m in client.seen] == [
        ("user", "first"),
        ("assistant", "one"),
        ("user", "second"),
    ]


async def test_system_prompt_is_prepended_and_never_logged() -> None:
    client = ScriptedClient(completed("ok"))
    session = new_session()

    await drain(agent(client, system_prompt="be brief").run("hi", session=session))

    assert client.seen[0] == SystemMessage(content="be brief")
    assert not any("be brief" in str(e) for e in session.events())


async def test_provider_failure_ends_the_turn_without_hanging() -> None:
    client = ScriptedClient([TextChunk(text="par"), Failed(reason="502 upstream")])
    session = new_session()

    events = await asyncio.wait_for(drain(agent(client).run("hi", session=session)), timeout=1)

    assert events[-1] == AgentFailed(reason="502 upstream")
    assert session.events()[-1] == TurnEnd(turn=0, reason="failed")
    assert not any(isinstance(e, AssistantMessageEvent) for e in session.events())


async def test_stream_without_a_terminal_is_a_failure_not_a_success() -> None:
    client = ScriptedClient([TextChunk(text="half")])
    session = new_session()

    events = await drain(agent(client).run("hi", session=session))

    assert events[-1] == AgentFailed(reason=NO_TERMINAL)
    assert session.events()[-1].reason == "failed"


async def test_cancelled_turn_finalizes_the_prefix_the_user_saw() -> None:
    client = HangingClient("partial answer")
    session = new_session()

    async with aclosing(agent(client).run("hi", session=session)) as run:
        first = await run.__anext__()
        assert first == TextChunk(text="partial answer")

    message = next(e for e in session.events() if isinstance(e, AssistantMessageEvent))
    assert message.interrupted is True
    assert message.message.content == "partial answer"
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")
    assert client.closed is True


async def test_cancelled_before_any_text_records_no_assistant_message() -> None:
    client = HangingClient("")
    session = new_session()

    async with aclosing(agent(client).run("hi", session=session)) as run:
        await run.__anext__()

    assert not any(isinstance(e, AssistantMessageEvent) for e in session.events())
    assert session.events()[-1] == TurnEnd(turn=0, reason="cancelled")


async def test_a_turn_is_closed_exactly_once() -> None:
    client = ScriptedClient(completed("ok"))
    session = new_session()

    await drain(agent(client).run("hi", session=session))

    assert sum(isinstance(e, TurnEnd) for e in session.events()) == 1


@pytest.mark.parametrize("turns", [1, 2, 3])
async def test_turn_numbers_are_derived_from_the_log(turns: int) -> None:
    client = ScriptedClient(completed("ok"))
    session = new_session()

    for _ in range(turns):
        await drain(agent(client).run("hi", session=session))

    starts = [e.turn for e in session.events() if isinstance(e, TurnStart)]
    assert starts == list(range(turns))


async def test_usage_travels_with_the_assistant_message() -> None:
    from harness.llm.stream import Usage

    usage = Usage(input_tokens=11, output_tokens=3)
    client = ScriptedClient([TextChunk(text="ok"), Completed(full_text="ok", usage=usage)])
    session = new_session()

    await drain(agent(client).run("hi", session=session))

    message = next(e for e in session.events() if isinstance(e, AssistantMessageEvent))
    assert message.usage == usage
