"""The JSONL backend: round-trip, lazy materialization, and what it refuses."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from harness.llm.messages import AssistantMessage, UserMessage
from harness.llm.stream import TextChunk
from harness.session.models import (
    AssistantChunk,
    AssistantMessageEvent,
    SessionHeader,
    TurnEnd,
    TurnStart,
    UserMessageEvent,
)
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)


def header(session_id: str = "s") -> SessionHeader:
    return SessionHeader(id=session_id, created_at=datetime(2026, 1, 1, tzinfo=UTC))


def a_turn(turn: int = 0, *, text: str = "hi") -> list:
    return [
        TurnStart(turn=turn),
        UserMessageEvent(turn=turn, message=UserMessage(content=text)),
        AssistantChunk(turn=turn, step=0, chunk=TextChunk(text="ok")),
        AssistantMessageEvent(turn=turn, step=0, message=AssistantMessage(content="ok")),
        TurnEnd(turn=turn, reason="completed"),
    ]


@pytest.fixture
def store(tmp_path) -> JsonlSessionRepository:
    return JsonlSessionRepository(tmp_path / "sessions")


# ── round-trip ────────────────────────────────────────────────────────────────


async def test_events_round_trip_identically(store) -> None:
    await store.create(header())
    events = a_turn()
    await store.append("s", events)

    loaded_header, loaded = await store.load("s")

    assert loaded_header.id == "s"
    assert loaded == events


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


# ── lazy materialization ──────────────────────────────────────────────────────


async def test_create_writes_nothing(store, tmp_path) -> None:
    """A conversation opened and abandoned leaves no trace."""
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


# ── the title ─────────────────────────────────────────────────────────────────


async def test_the_title_comes_from_the_first_user_message(store) -> None:
    await store.create(header())
    await store.append("s", a_turn(text="how do generators work?"))

    loaded_header, _ = await store.load("s")

    assert loaded_header.title == "how do generators work?"


async def test_a_long_first_message_is_capped_but_the_log_keeps_it_whole(store) -> None:
    """The title is a label, not a summary — the full message stays in the log."""
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


# ── continuity ────────────────────────────────────────────────────────────────


async def test_a_fresh_instance_counts_the_stored_log(store, tmp_path) -> None:
    """A restarted process reads the count off disk rather than assuming zero —
    otherwise its first append would silently overwrite the header."""
    await store.create(header())
    await store.append("s", a_turn(0))

    reopened = JsonlSessionRepository(tmp_path / "sessions")

    assert await reopened.stored_count("s") == 5
    await reopened.append("s", a_turn(1))
    _, loaded = await reopened.load("s")
    assert len(loaded) == 10


async def test_stored_count_is_zero_before_anything_is_written(store) -> None:
    """Including for a session that was created and then abandoned."""
    await store.create(header())

    assert await store.stored_count("s") == 0


async def test_stored_count_tracks_appends(store) -> None:
    await store.create(header())
    await store.append("s", a_turn(0))

    assert await store.stored_count("s") == 5


# ── what it refuses, and what it tolerates ────────────────────────────────────


async def test_a_torn_final_line_is_dropped(store, tmp_path) -> None:
    """A crash mid-write leaves one. Everything before it was committed."""
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"type":"turn/start","tur')  # no newline: torn

    _, loaded = await store.load("s")

    assert len(loaded) == 5


async def test_a_malformed_line_in_the_middle_is_corruption(store, tmp_path) -> None:
    """Skipping it would hand the model a history with a hole and no way to know."""
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    lines = path.read_text().splitlines(keepends=True)
    lines[2] = "{not json}\n"
    path.write_text("".join(lines))

    with pytest.raises(SessionCorruptionError, match="line 3"):
        await store.load("s")


async def test_a_complete_but_invalid_final_line_is_also_corruption(store, tmp_path) -> None:
    """Terminated by a newline means the write finished — so it is not torn,
    it is wrong."""
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"type":"nope"}\n')

    with pytest.raises(SessionCorruptionError):
        await store.load("s")


async def test_an_unknown_format_version_refuses_and_names_the_file(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    lines = path.read_text().splitlines(keepends=True)
    lines[0] = lines[0].replace('"version":1', '"version":99')
    path.write_text("".join(lines))

    with pytest.raises(SessionFormatUnsupportedError, match="s.jsonl"):
        await store.load("s")


async def test_an_empty_file_has_no_header(store, tmp_path) -> None:
    root = tmp_path / "sessions"
    root.mkdir(parents=True)
    (root / "s.jsonl").write_text("")

    with pytest.raises(SessionCorruptionError, match="no header"):
        await store.load("s")


@pytest.mark.parametrize("bad", ["../escape", "a/b", "..", "a\\b"])
async def test_an_unsafe_id_cannot_reach_outside_the_root(store, bad) -> None:
    with pytest.raises(ValueError, match="unsafe session id"):
        await store.load(bad)


# ── listing ───────────────────────────────────────────────────────────────────


async def test_list_returns_newest_first(store) -> None:
    for n, day in enumerate([3, 1, 2]):
        h = SessionHeader(id=f"s{n}", created_at=datetime(2026, 1, day, tzinfo=UTC))
        await store.create(h)
        await store.append(f"s{n}", a_turn())

    assert [h.id for h in await store.list()] == ["s0", "s2", "s1"]


async def test_list_reads_only_line_one(store, tmp_path) -> None:
    """The point of the whole layout: a conversation index never parses a log.

    Proven by corrupting line 2 — listing must not care.
    """
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    lines = path.read_text().splitlines(keepends=True)
    lines[1] = "{total garbage}\n"
    path.write_text("".join(lines))

    listed = await store.list()

    assert [h.id for h in listed] == ["s"]
    # …and the same file still refuses to load, so the damage is not hidden.
    with pytest.raises(SessionCorruptionError):
        await store.load("s")


async def test_one_corrupt_header_does_not_break_the_whole_list(store, tmp_path) -> None:
    await store.create(header("good"))
    await store.append("good", a_turn())
    (tmp_path / "sessions" / "broken.jsonl").write_text("{not a header}\n")

    assert [h.id for h in await store.list()] == ["good"]


async def test_listing_an_absent_root_is_empty_not_an_error(store) -> None:
    assert await store.list() == []
