"""Clearing a chat wipes its file in place: same id and title, numbering carried on."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from harness.agent.compaction import CompactionRefused, check_can_compact
from harness.agent.compaction.history import PRUNE_KEEP
from harness.agent.compaction.service import NOTHING
from harness.bots import ASSISTANT_ID
from harness.llm.client import LLMClient
from harness.llm.messages import (
    ApplicationMessage,
    Message,
    ToolMessage,
    ToolReference,
    ToolSpec,
    UserMessage,
)
from harness.llm.stream import StreamEvent, TextChunk
from harness.session.compaction import CompactionEnd
from harness.session.log import Numbered, Session
from harness.session.models import (
    ApprovalGrant,
    BotInstructionsEvent,
    ChatCleared,
    ToolResultEvent,
    TurnStart,
    UserMessageEvent,
)
from harness.session.service import SessionService
from tests.unit.fakes import ScriptedClient
from tests.unit.helpers import agent_over, durable_service, run_store
from tests.unit.test_compaction_service import tool_turn


async def _chat_with_history(root: Path) -> tuple[SessionService, Session]:
    """A stored chat with instructions, a grant, a summary, selected tools and usage."""
    service = durable_service(root)
    session = await service.create()
    session.append(BotInstructionsEvent(name="b", instructions="BE BRIEF"))
    session.append(ApprovalGrant(turn=0, tool="fs__write_file"))
    session.append(CompactionEnd(turn=None, message=ApplicationMessage(content="SUMMARY")))
    for turn in range(PRUNE_KEEP + 2):
        tool_turn(session, turn, f"call{turn}", "big")
    session.append(
        ToolResultEvent(
            turn=0,
            step=0,
            message=ToolMessage(
                tool_call_id="call0", content=(ToolReference(tool_name="fs__read_file"),)
            ),
        )
    )
    await service.flush(session)
    return service, await service.read(session.id)


async def test_a_clear_keeps_the_id_and_numbers_on_past_what_it_wiped(tmp_path) -> None:
    service, before = await _chat_with_history(tmp_path / "sessions")

    await service.clear(before.id)

    after = await service.read(before.id)
    wiped = len(before.events())
    assert after.header == before.header.model_copy(
        update={"numbered_from": before.header.numbered_from + wiped}
    )
    assert after.id == "c0"
    assert after.events() == [ChatCleared()]


async def test_after_a_clear_new_events_number_on_and_read_back_under_the_new_header(
    tmp_path,
) -> None:
    root = tmp_path / "sessions"
    service, before = await _chat_with_history(root)
    wiped = len(before.events())
    await service.clear(before.id)

    session = await service.resume(before.id)
    assert session.next_number() == wiped + 1
    session.append(TurnStart(turn=0))
    await service.flush(session)

    reread = await durable_service(root).read(before.id)
    assert reread.header == session.header
    assert reread.header.numbered_from == wiped
    assert reread.numbered_events_from(0) == [
        Numbered(wiped, ChatCleared()),
        Numbered(wiped + 1, TurnStart(turn=0)),
    ]
    assert reread.next_number() == wiped + 2


async def test_clearing_twice_keeps_counting_up(tmp_path) -> None:
    service, before = await _chat_with_history(tmp_path / "sessions")
    wiped = len(before.events())
    await service.clear(before.id)
    between = await service.resume(before.id)
    tool_turn(between, 0, "next", "r")
    await service.flush(between)

    await service.clear(before.id)

    after = await service.read(before.id)
    assert after.header.numbered_from == wiped + len(between.events())
    assert after.events() == [ChatCleared()]


async def test_after_a_clear_the_model_sees_nothing_from_before(tmp_path) -> None:
    service, before = await _chat_with_history(tmp_path / "sessions")
    agent = agent_over(ScriptedClient([]))
    assert UserMessage(content="SUMMARY") in agent.request_messages(before)

    await service.clear(before.id)
    session = await service.resume(before.id)
    session.append(UserMessageEvent(turn=0, message=UserMessage(content="fresh")))

    assert agent.request_messages(session) == [UserMessage(content="fresh")]


async def test_after_a_clear_nothing_is_left_to_compact_granted_or_selected(tmp_path) -> None:
    service, before = await _chat_with_history(tmp_path / "sessions")
    check_can_compact(before)
    assert before.tools_granted() and before.tools_selected() and before.context_size()

    await service.clear(before.id)

    after = await service.resume(before.id)
    with pytest.raises(CompactionRefused) as refused:
        check_can_compact(after)
    assert refused.value.reason == NOTHING
    assert after.tools_granted() == frozenset()
    assert after.tools_selected() == ()
    assert after.context_size() is None


class SlowToLetGo(LLMClient):
    """Streams a chunk and hangs; once cancelled, takes a few loop turns to let go."""

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        try:
            yield TextChunk(text="thinking")
            await asyncio.Event().wait()
        finally:
            for _ in range(5):
                await asyncio.sleep(0)


async def test_a_clear_keeps_the_chat_busy_from_its_start_until_it_settles(tmp_path) -> None:
    service = durable_service(tmp_path / "sessions")
    runs = run_store(service, SlowToLetGo())
    session = await service.create(ASSISTANT_ID)
    turn = runs.start(session, "the secret word is PELICAN")
    while not any(event.type == "assistant/chunk" for event in session.events()):
        await asyncio.sleep(0)

    clearing = runs.clear(session)
    assert not turn.settled
    while not clearing.settled:
        assert runs.active(session.id) is clearing
        await asyncio.sleep(0)

    assert turn.settled
    assert runs.active(session.id) is None
    assert clearing.session.events() == [ChatCleared()]
    assert (await service.read(session.id)).events() == [ChatCleared()]
