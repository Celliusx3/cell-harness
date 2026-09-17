"""The compaction service: prune first, summarize when that is not enough, fail open."""

from __future__ import annotations

from collections.abc import AsyncIterator

from harness.agent.compaction import COMPACT_AT, PRUNE_KEEP, CompactionService
from harness.agent.compaction.prompt import INSTRUCTION, PREAMBLE
from harness.llm.client import LLMClient
from harness.llm.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    ToolSpec,
    UserMessage,
)
from harness.llm.stream import Failed, StreamEvent, Usage
from harness.session.compaction import CompactionEnd, CompactionPrune, CompactionStart
from harness.session.derive import derive_messages
from harness.session.models import (
    AssistantMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.skills import SKILL
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import new_session

SKILL_BODY = '<skill name="find-place">\nWalk the reel to a place.\n</skill>'


def tool_turn(session, turn: int, call_id: str, result: str, name: str = "execute_typescript"):
    call = ToolCall(id=call_id, name=name, arguments="{}")
    session.append(TurnStart(turn=turn))
    session.append(UserMessageEvent(turn=turn, message=UserMessage(content=f"q{turn}")))
    session.append(
        AssistantMessageEvent(
            turn=turn, step=0, message=AssistantMessage(content="", tool_calls=(call,))
        )
    )
    session.append(ToolCallEvent(turn=turn, step=0, call=call))
    session.append(
        ToolResultEvent(
            turn=turn, step=0, message=ToolMessage(tool_call_id=call_id, content=result)
        )
    )
    session.append(
        AssistantMessageEvent(
            turn=turn,
            step=1,
            message=AssistantMessage(content=f"a{turn}"),
            usage=Usage(input_tokens=10_000, output_tokens=100),
        )
    )
    session.append(TurnEnd(turn=turn, reason="completed"))


def compactor(client: LLMClient, context: int | None = 12_000) -> CompactionService:
    return CompactionService(client=client, model="m", system_prompt="SYS", context_tokens=context)


async def drain(gen: AsyncIterator) -> list:
    return [e async for e in gen]


def kinds(session) -> list[str]:
    return [e.type for e in session.events() if e.type.startswith("compaction/")]


def test_due_needs_a_window_and_a_measurement() -> None:
    session = new_session()
    assert not compactor(ScriptedClient([])).due(session)  # nothing measured yet
    tool_turn(session, 0, "c0", "r")  # 10,100 used
    assert not compactor(ScriptedClient([]), context=None).due(session)
    assert not compactor(ScriptedClient([]), context=20_000).due(session)  # 10,100 < 16,000
    assert compactor(ScriptedClient([]), context=12_000).due(session)  # 10,100 >= 9,600
    assert COMPACT_AT == 0.8


async def test_when_due_old_tool_results_are_pruned_before_any_summary() -> None:
    session = new_session()
    for turn in range(PRUNE_KEEP + 2):
        tool_turn(session, turn, f"c{turn}", "big")
    client = ScriptedClient(completed("never"))

    yielded = await drain(compactor(client).before_step(session, turn=9))

    assert client.calls == 0
    assert yielded == [CompactionPrune(turn=9, call_ids=("c0", "c1"))]
    assert kinds(session) == ["compaction/prune"]


async def test_skill_results_are_never_pruned() -> None:
    session = new_session()
    tool_turn(session, 0, "s0", SKILL_BODY, name=SKILL)
    for turn in range(1, PRUNE_KEEP + 3):
        tool_turn(session, turn, f"c{turn}", "big")

    yielded = await drain(compactor(ScriptedClient([])).before_step(session, turn=9))

    assert yielded == [CompactionPrune(turn=9, call_ids=("c1", "c2"))]


async def test_nothing_happens_below_the_line() -> None:
    session = new_session()
    for turn in range(6):
        tool_turn(session, turn, f"c{turn}", "big")
    assert (
        await drain(compactor(ScriptedClient([]), context=100_000).before_step(session, turn=9))
        == []
    )
    assert kinds(session) == []


async def test_with_nothing_to_prune_it_summarizes() -> None:
    """The summary request is the conversation as the model sees it plus the
    instruction, no tools; the end carries the rendered message."""
    session = new_session()
    tool_turn(session, 0, "s0", SKILL_BODY, name=SKILL)
    tool_turn(session, 1, "c1", "recent")
    client = ScriptedClient(completed("THE SUMMARY"))

    yielded = await drain(compactor(client).before_step(session, turn=2))

    assert client.calls == 1
    assert client.seen_tools is None
    assert client.seen[0] == SystemMessage(content="SYS")
    assert client.seen[-1] == UserMessage(content=INSTRUCTION)
    assert client.seen[1:-1] == derive_messages(session.events()[:-2])
    assert [e.type for e in yielded] == ["compaction/start", "compaction/end"]
    start, end = yielded
    assert start == CompactionStart(turn=2, trigger="auto", tokens=10_100)
    assert isinstance(end, CompactionEnd) and end.message is not None
    assert end.message.content.startswith(PREAMBLE)
    assert "<compacted-summary>\nTHE SUMMARY\n</compacted-summary>" in end.message.content
    assert SKILL_BODY in end.message.content
    assert derive_messages(session.events()) == [UserMessage(content=end.message.content)]


async def test_a_skill_typed_as_a_slash_command_is_retained_too() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(
        UserMessageEvent(
            turn=0, message=UserMessage(content=f"/find-place this reel\n\n{SKILL_BODY}")
        )
    )
    session.append(
        AssistantMessageEvent(
            turn=0,
            step=0,
            message=AssistantMessage(content="ok"),
            usage=Usage(input_tokens=10_000, output_tokens=1),
        )
    )
    session.append(TurnEnd(turn=0, reason="completed"))

    await drain(compactor(ScriptedClient(completed("S"))).before_step(session, turn=1))

    end = session.events()[-1]
    assert isinstance(end, CompactionEnd) and end.message is not None
    assert end.message.content.count(SKILL_BODY) == 1


async def test_a_failed_summary_is_logged_and_changes_nothing() -> None:
    session = new_session()
    tool_turn(session, 0, "c0", "r")
    before = derive_messages(session.events())

    yielded = await drain(
        compactor(ScriptedClient([Failed(reason="boom")])).before_step(session, turn=1)
    )

    assert [e.type for e in yielded] == ["compaction/start", "compaction/end"]
    assert yielded[1] == CompactionEnd(turn=1, error="summary request failed: boom")
    assert derive_messages(session.events()) == before


async def test_an_empty_summary_is_a_failure() -> None:
    session = new_session()
    tool_turn(session, 0, "c0", "r")
    yielded = await drain(compactor(ScriptedClient(completed("   "))).before_step(session, turn=1))
    assert isinstance(yielded[1], CompactionEnd) and yielded[1].message is None
    assert yielded[1].error is not None


async def test_a_summarizer_that_raises_fails_open() -> None:
    class Broken(LLMClient):
        async def stream_completion(
            self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
        ) -> AsyncIterator[StreamEvent]:
            raise RuntimeError("adapter bug")
            yield  # pragma: no cover

    session = new_session()
    tool_turn(session, 0, "c0", "r")
    yielded = await drain(compactor(Broken()).before_step(session, turn=1))
    assert isinstance(yielded[1], CompactionEnd) and "adapter bug" in (yielded[1].error or "")


async def test_a_summary_of_only_a_summary_is_refused() -> None:
    """Bounded: once everything is one summary there is nothing left to shrink."""
    session = new_session()
    tool_turn(session, 0, "c0", "r")
    client = ScriptedClient(completed("S"))
    await drain(compactor(client).before_step(session, turn=1))
    assert client.calls == 1

    assert await drain(compactor(client).recover(session, turn=1)) == []
    assert client.calls == 1
    assert compactor(client).refusal(session) == "nothing to compact"


async def test_an_unanswered_call_refuses_a_summary() -> None:
    session = new_session()
    call = ToolCall(id="p1", name="get_location", arguments="{}")
    session.append(TurnStart(turn=0))
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="where am I")))
    session.append(
        AssistantMessageEvent(
            turn=0,
            step=0,
            message=AssistantMessage(content="", tool_calls=(call,)),
            usage=Usage(input_tokens=10_000, output_tokens=1),
        )
    )
    session.append(ToolCallEvent(turn=0, step=0, call=call))
    session.append(TurnEnd(turn=0, reason="pending"))
    client = ScriptedClient(completed("S"))

    assert compactor(client).refusal(session) == "a client request is still unanswered"
    assert await drain(compactor(client).compact_now(session)) == []
    assert client.calls == 0


async def test_recover_ignores_the_line_and_manual_says_so() -> None:
    session = new_session()
    tool_turn(session, 0, "c0", "r")
    client = ScriptedClient(completed("S"))

    yielded = await drain(compactor(client, context=1_000_000).recover(session, turn=1))
    assert isinstance(yielded[0], CompactionStart) and yielded[0].trigger == "overflow"

    tool_turn(session, 1, "c1", "r")
    yielded = await drain(compactor(client, context=None).compact_now(session))
    assert yielded[0] == CompactionStart(turn=None, trigger="manual", tokens=10_100)
    assert isinstance(yielded[1], CompactionEnd) and yielded[1].message is not None


async def test_closing_the_generator_mid_summary_closes_the_bracket() -> None:
    from tests.unit.fakes import HangingClient

    session = new_session()
    tool_turn(session, 0, "c0", "r")
    gen = compactor(HangingClient("")).before_step(session, turn=1)
    first = await gen.__anext__()
    assert isinstance(first, CompactionStart)
    await gen.aclose()

    end = session.events()[-1]
    assert isinstance(end, CompactionEnd) and end.message is None and end.error
