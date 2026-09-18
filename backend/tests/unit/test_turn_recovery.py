"""What `drive` commits to around an overflow: the refused step's shape, the
text on screen when the recovery itself is cut short, and which failures are
never retried."""

from __future__ import annotations

import asyncio

from harness.agent.compaction import CompactionService
from harness.agent.events import AgentCompleted, AgentFailed
from harness.agent.loop import LoopAgent
from harness.llm.client import LLMClient
from harness.llm.messages import AssistantMessage, UserMessage
from harness.llm.stream import CONTEXT_WINDOW_EXCEEDED, Completed, Failed, TextChunk, Usage
from harness.session.log import Session
from harness.session.models import (
    AssistantMessageEvent,
    StepStart,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from tests.unit.helpers import cancel_mid_turn, drain, loop_agent, new_session


def asks_for_a_summary(messages, tools) -> bool:
    return tools is None and any(
        "compaction engine" in m.content for m in messages if isinstance(m, UserMessage)
    )


def compacting(client: LLMClient) -> LoopAgent:
    return loop_agent(
        client,
        compaction=CompactionService(
            client=client, model="m", system_prompt="", context_tokens=None
        ),
    )


def seeded() -> Session:
    """A session with one finished turn, so a recovery has something to summarize."""
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="old")))
    session.append(
        AssistantMessageEvent(
            turn=0,
            step=0,
            message=AssistantMessage(content="a"),
            usage=Usage(input_tokens=1, output_tokens=1),
        )
    )
    session.append(TurnEnd(turn=0, reason="completed"))
    return session


def since_the_last_turn_start(session: Session) -> list[str]:
    types = [e.type for e in session.events()]
    return types[len(types) - types[::-1].index("turn/start") :]


async def test_a_retried_step_leaves_the_refused_one_without_an_end() -> None:
    class Overflows(LLMClient):
        def __init__(self) -> None:
            self.refused = False

        async def stream_completion(self, messages, model, *, tools=None):
            if asks_for_a_summary(messages, tools):
                yield Completed(full_text="SUMMARY")
                return
            if not self.refused:
                self.refused = True
                yield TextChunk(text="par")
                yield Failed(reason="too long", code=CONTEXT_WINDOW_EXCEEDED)
                return
            yield Completed(full_text="recovered")

    session = seeded()

    events = await drain(compacting(Overflows()).run("go", session=session))

    assert events[-1] == AgentCompleted(text="recovered")
    assert since_the_last_turn_start(session) == [
        "user/message",
        "step/start",
        "assistant/chunk",
        "assistant/chunk",
        "compaction/start",
        "compaction/end",
        "step/start",
        "assistant/chunk",
        "assistant/message",
        "step/end",
        "turn/end",
    ]
    assert [e.step for e in session.events() if isinstance(e, StepStart)] == [0, 1]


async def test_cancelling_during_recovery_logs_the_text_the_person_saw() -> None:
    class OverflowsThenHangs(LLMClient):
        async def stream_completion(self, messages, model, *, tools=None):
            if asks_for_a_summary(messages, tools):
                await asyncio.Event().wait()
            yield TextChunk(text="par")
            yield Failed(reason="too long", code=CONTEXT_WINDOW_EXCEEDED)

    session = seeded()

    await cancel_mid_turn(compacting(OverflowsThenHangs()), session, "go")

    assert since_the_last_turn_start(session) == [
        "user/message",
        "step/start",
        "assistant/chunk",
        "assistant/chunk",
        "compaction/start",
        "compaction/end",
        "assistant/message",
        "step/end",
        "turn/end",
    ]
    message = session.events()[-3]
    assert isinstance(message, AssistantMessageEvent)
    assert (message.step, message.interrupted, message.message.content) == (0, True, "par")
    assert session.events()[-1] == TurnEnd(turn=1, reason="cancelled")


async def test_a_failure_without_a_code_is_not_retried_even_with_compaction() -> None:
    class Refuses(LLMClient):
        async def stream_completion(self, messages, model, *, tools=None):
            yield Failed(reason="502 upstream")

    session = seeded()

    events = await drain(compacting(Refuses()).run("go", session=session))

    assert events[-1] == AgentFailed(reason="502 upstream")
    assert not any(e.type.startswith("compaction/") for e in session.events())
