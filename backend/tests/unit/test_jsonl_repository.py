"""The JSONL backend: round-trip, lazy materialization, the title, continuity."""

from __future__ import annotations

import pytest

from harness.llm.messages import ApplicationMessage, ToolCall, ToolMessage, UserMessage
from harness.session.models import (
    ApplicationMessageEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import SessionNotFoundError
from harness.tools.definition import ToolUi
from tests.unit.jsonl_helpers import a_turn, header, repository


@pytest.fixture
def store(tmp_path) -> JsonlSessionRepository:
    return repository(tmp_path)


async def test_events_round_trip_identically(store) -> None:
    await store.create(header())
    events = a_turn()
    await store.append("s", events)

    loaded_header, loaded = await store.load("s")

    assert loaded_header.id == "s"
    assert loaded == events


async def test_a_tool_result_with_an_app_round_trips(store) -> None:
    await store.create(header())
    result = ToolResultEvent(
        turn=0,
        step=0,
        message=ToolMessage(tool_call_id="c1", content="42"),
        ui=ToolUi(server="srv", resource_uri="ui://srv/app.html", data={"rows": [1, 2]}),
    )
    await store.append(
        "s",
        [
            TurnStart(turn=0),
            ToolCallEvent(turn=0, step=0, call=ToolCall(id="c1", name="srv__x", arguments="{}")),
            result,
        ],
    )

    _, loaded = await store.load("s")

    assert loaded[-1] == result


async def test_a_tool_result_logged_before_apps_existed_still_loads(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(
            '{"type":"tool/result","turn":1,"step":0,'
            '"message":{"role":"tool","tool_call_id":"c1","content":"42"},"error":null}\n'
        )

    _, loaded = await store.load("s")

    assert isinstance(loaded[-1], ToolResultEvent)
    assert loaded[-1].ui is None


async def test_a_thousand_events_round_trip(store) -> None:
    await store.create(header())
    events = [TurnStart(turn=n) for n in range(1000)]
    await store.append("s", events)

    _, loaded = await store.load("s")

    assert loaded == events


async def test_appends_accumulate(store) -> None:
    await store.create(header())
    await store.append("s", a_turn(0))
    await store.append("s", a_turn(1))

    _, loaded = await store.load("s")

    assert len(loaded) == 10
    assert [e.turn for e in loaded if isinstance(e, TurnStart)] == [0, 1]


async def test_create_writes_nothing(store, tmp_path) -> None:
    await store.create(header())

    assert not (tmp_path / "sessions" / "s.jsonl").exists()
    assert await store.list() == []


async def test_an_empty_batch_is_a_no_op(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", [])

    assert not (tmp_path / "sessions" / "s.jsonl").exists()


async def test_appending_to_an_uncreated_session_fails(store) -> None:
    with pytest.raises(SessionNotFoundError):
        await store.append("ghost", a_turn())


async def test_loading_an_absent_session_fails(store) -> None:
    with pytest.raises(SessionNotFoundError):
        await store.load("ghost")


async def test_the_title_comes_from_the_first_user_message(store) -> None:
    await store.create(header())
    await store.append("s", a_turn(text="how do generators work?"))

    loaded_header, _ = await store.load("s")

    assert loaded_header.title == "how do generators work?"


async def test_a_guardrail_message_never_becomes_the_title(store) -> None:
    await store.create(header())
    await store.append(
        "s",
        [
            TurnStart(turn=0),
            ApplicationMessageEvent(turn=0, message=ApplicationMessage(content="Note: …")),
            UserMessageEvent(turn=0, message=UserMessage(content="what the human said")),
        ],
    )

    loaded_header, _ = await store.load("s")

    assert loaded_header.title == "what the human said"


async def test_a_long_first_message_is_capped_but_the_log_keeps_it_whole(store) -> None:
    long = "x" * 500
    await store.create(header())
    await store.append("s", a_turn(text=long))

    loaded_header, events = await store.load("s")

    assert len(loaded_header.title) == 120
    message = next(e for e in events if isinstance(e, UserMessageEvent))
    assert message.message.content == long


async def test_the_title_is_stamped_once_not_rewritten(store) -> None:
    await store.create(header())
    await store.append("s", a_turn(text="first"))
    await store.append("s", a_turn(1, text="second"))

    loaded_header, _ = await store.load("s")

    assert loaded_header.title == "first"


async def test_a_fresh_instance_counts_the_stored_log(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn(0))

    reopened = JsonlSessionRepository(tmp_path / "sessions")

    assert await reopened.stored_count("s") == 5
    await reopened.append("s", a_turn(1))
    _, loaded = await reopened.load("s")
    assert len(loaded) == 10


async def test_stored_count_is_zero_before_anything_is_written(store) -> None:
    await store.create(header())

    assert await store.stored_count("s") == 0


async def test_stored_count_tracks_appends(store) -> None:
    await store.create(header())
    await store.append("s", a_turn(0))

    assert await store.stored_count("s") == 5


async def test_the_chats_mapped_to_a_conversation_can_be_found(tmp_path) -> None:
    from harness.channels.repositories.jsonl import JsonlChatRepository
    from harness.channels.repository import ChatState

    chats = JsonlChatRepository(tmp_path / "chats")
    await chats.save(ChatState(channel="telegram", chat_id="1", conversation_id="c0"))
    await chats.save(ChatState(channel="discord", chat_id="9", conversation_id="c0"))
    await chats.save(ChatState(channel="telegram", chat_id="2", conversation_id="c1"))
    await chats.set_cursor("telegram", "77")

    found = await chats.chats_of("c0")
    assert sorted((s.channel, s.chat_id) for s in found) == [("discord", "9"), ("telegram", "1")]
    assert await chats.chats_of("nope") == []


async def test_files_that_are_not_chats_do_not_break_the_lookup(tmp_path) -> None:
    from harness.channels.repositories.jsonl import JsonlChatRepository
    from harness.channels.repository import ChatState

    chats = JsonlChatRepository(tmp_path / "chats")
    await chats.save(ChatState(channel="discord", chat_id="9", conversation_id="c0"))
    (tmp_path / "chats" / "offset.json").write_text('{"offset": 993566173}')
    (tmp_path / "chats" / "chat-1932139557.json").write_text('{"chat_id": 1932139557}')
    (tmp_path / "chats" / "notes.txt").write_text("not json at all")

    found = await chats.chats_of("c0")
    assert [(s.channel, s.chat_id) for s in found] == [("discord", "9")]
