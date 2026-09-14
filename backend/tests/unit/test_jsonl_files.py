"""The JSONL backend's files: what a damaged one costs, and what a listing reads."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from harness.session.models import SessionHeader
from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import SessionCorruptionError, SessionFormatUnsupportedError
from tests.unit.jsonl_helpers import a_turn, header, repository


@pytest.fixture
def store(tmp_path) -> JsonlSessionRepository:
    return repository(tmp_path)


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
