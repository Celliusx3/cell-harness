"""The JSONL backend's files: what a damaged one costs, what an old one holds, deleting one."""

from __future__ import annotations

import pytest

from harness.session.repositories.jsonl import JsonlSessionRepository
from harness.session.repository import (
    SessionCorruptionError,
    SessionFormatUnsupportedError,
    SessionNotFoundError,
)
from tests.unit.jsonl_helpers import a_turn, header, repository


@pytest.fixture
def store(tmp_path) -> JsonlSessionRepository:
    return repository(tmp_path)


async def test_a_torn_final_line_is_dropped(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"type":"turn/start","tur')  # no newline: torn

    _, loaded = await store.load("s")

    assert len(loaded) == 5


async def test_a_malformed_line_in_the_middle_is_corruption(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    lines = path.read_text().splitlines(keepends=True)
    lines[2] = "{not json}\n"
    path.write_text("".join(lines))

    with pytest.raises(SessionCorruptionError, match="line 3"):
        await store.load("s")


async def test_a_complete_but_invalid_final_line_is_also_corruption(store, tmp_path) -> None:
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


async def test_a_header_written_with_a_title_still_loads(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn())
    path = tmp_path / "sessions" / "s.jsonl"
    lines = path.read_text().splitlines(keepends=True)
    lines[0] = lines[0].replace('"version":1', '"version":1,"title":"from before"')
    path.write_text("".join(lines))
    assert '"title":"from before"' in path.read_text()

    loaded_header, loaded = await store.load("s")

    assert loaded_header == header()
    assert len(loaded) == 5


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


async def test_a_deleted_session_is_gone_and_cannot_be_loaded(store, tmp_path) -> None:
    await store.create(header())
    await store.append("s", a_turn())

    await store.delete("s")

    assert not (tmp_path / "sessions" / "s.jsonl").exists()
    assert await store.stored_count("s") == 0
    with pytest.raises(SessionNotFoundError):
        await store.load("s")


async def test_deleting_a_session_never_written_is_fine(store, tmp_path) -> None:
    await store.create(header())

    await store.delete("s")

    with pytest.raises(SessionNotFoundError):
        await store.append("s", a_turn())
