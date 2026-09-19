"""The loop compacts on its own: before a step when big, and when the provider refuses."""

from __future__ import annotations

from collections.abc import AsyncIterator

from harness.agent.compaction import CompactionService
from harness.agent.compaction.prompt import OPEN
from harness.agent.loop import LoopAgent
from harness.llm.client import LLMClient
from harness.llm.messages import Message, ToolSpec, UserMessage
from harness.llm.stream import (
    CONTEXT_WINDOW_EXCEEDED,
    Completed,
    Failed,
    StreamEvent,
    TextChunk,
    Usage,
)
from harness.session.derive import derive_messages
from tests.unit.helpers import drain, new_session


class SizedClient(LLMClient):
    """Answers each turn, reporting a growing context so compaction is provoked."""

    def __init__(self, *, per_turn: int) -> None:
        self._per_turn = per_turn
        self.turns = 0
        self.summaries = 0
        self.seen: list[Message] = []

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        self.seen = list(messages)
        if tools is None and any(
            "compaction engine" in m.content for m in messages if isinstance(m, UserMessage)
        ):
            self.summaries += 1
            yield Completed(full_text="INTENT: keep going. NEXT: answer.")
            return
        self.turns += 1
        used = self._per_turn * (self.turns + 1)
        yield TextChunk(text="ok")
        yield Completed(full_text="ok", usage=Usage(input_tokens=used, output_tokens=10))


def agent_with(client: LLMClient, context: int | None) -> LoopAgent:
    return LoopAgent(
        name="t",
        model="m",
        client=client,
        system_prompt="SYS",
        compaction=CompactionService(
            client=client, model="m", system_prompt="SYS", context_tokens=context
        ),
    )


async def test_a_long_conversation_compacts_and_keeps_going() -> None:
    client = SizedClient(per_turn=2_000)
    agent = agent_with(client, context=20_000)
    session = new_session()

    for i in range(200):
        await drain(agent.run(f"message {i}", session=session))

    assert client.summaries >= 1
    users = [e for e in session.events() if e.type == "user/message"]
    assert len(users) == 200
    assert any(OPEN in m.content for m in client.seen if isinstance(m, UserMessage))


async def test_the_summary_survives_into_the_next_turn() -> None:
    client = SizedClient(per_turn=6_000)
    agent = agent_with(client, context=10_000)
    session = new_session()

    await drain(agent.run("first", session=session))
    await drain(agent.run("second", session=session))

    messages = derive_messages(session.events())
    assert isinstance(messages[0], UserMessage) and OPEN in messages[0].content


class OverflowingClient(LLMClient):
    """Refuses the first request with a size error, then answers."""

    def __init__(self) -> None:
        self.refusals = 0
        self.answered = False

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        if tools is None and any(
            "compaction engine" in m.content for m in messages if isinstance(m, UserMessage)
        ):
            yield Completed(full_text="SUMMARY")
            return
        if self.refusals == 0:
            self.refusals += 1
            yield Failed(reason="too long", code=CONTEXT_WINDOW_EXCEEDED)
            return
        self.answered = True
        yield Completed(full_text="recovered")


async def test_an_overflow_is_recovered_and_the_step_retried() -> None:
    client = OverflowingClient()
    agent = agent_with(client, context=None)
    session = new_session()
    from harness.llm.messages import AssistantMessage
    from harness.session.models import (
        AssistantMessageEvent,
        TurnEnd,
        TurnStart,
        UserMessageEvent,
    )

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

    events = await drain(agent.run("go", session=session))

    assert client.answered
    assert any(e.kind == "agent_completed" for e in events)
    kinds = [e.type for e in session.events() if e.type.startswith("compaction/")]
    assert "compaction/start" in kinds


async def test_an_overflow_with_nothing_to_shrink_fails_the_turn() -> None:
    class AlwaysOverflows(LLMClient):
        async def stream_completion(
            self, messages, model, *, tools=None
        ) -> AsyncIterator[StreamEvent]:
            yield Failed(reason="too long", code=CONTEXT_WINDOW_EXCEEDED)

    client = AlwaysOverflows()
    agent = agent_with(client, context=None)
    session = new_session()
    events = await drain(agent.run("go", session=session))

    assert any(e.kind == "agent_failed" for e in events)
