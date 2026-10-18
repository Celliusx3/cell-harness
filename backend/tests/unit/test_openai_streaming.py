"""Streamed lines read into chunks: which lines count, and each field kept only of its type."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from pydantic import JsonValue

from harness.llm import Usage
from harness.llm.adapters.openai._streaming import chunk_of, chunks_of
from harness.llm.adapters.openai.models.chunk import Chunk
from harness.llm.adapters.openai.models.tool_delta import ToolDelta

EMPTY = Chunk(text="", tool_deltas=(), usage=None, error=None)
SAID_A = Chunk(text="a", tool_deltas=(), usage=None, error=None)
DATA_A = "data: " + json.dumps({"choices": [{"delta": {"content": "a"}}]})


def chunk_sent(payload: dict[str, JsonValue]) -> Chunk:
    """The chunk of `payload` sent as one line."""
    return chunk_of(payload, json.dumps(payload))


async def lines_of(*lines: str) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def chunks_read(*lines: str) -> list[Chunk]:
    return [chunk async for chunk in chunks_of(lines_of(*lines))]


async def test_a_line_that_is_not_data_is_skipped() -> None:
    assert await chunks_read("event: message", ": keep-alive", "", DATA_A) == [SAID_A]


async def test_reading_stops_at_done_and_a_later_line_is_not_read() -> None:
    assert await chunks_read(DATA_A, "data: [DONE]", DATA_A) == [SAID_A]


async def test_a_line_that_is_not_json_is_skipped() -> None:
    assert await chunks_read("data: {not json", DATA_A) == [SAID_A]


@pytest.mark.parametrize("data", ["5", "null", '"text"', "[1]"])
async def test_a_line_whose_json_is_not_an_object_is_skipped(data: str) -> None:
    assert await chunks_read(f"data: {data}", DATA_A) == [SAID_A]


async def test_an_error_line_becomes_a_chunk_carrying_the_lines_data() -> None:
    error = json.dumps({"error": {"message": "overloaded"}})

    chunks = await chunks_read(f"data: {error}  ")

    assert chunks == [Chunk(text="", tool_deltas=(), usage=None, error=error)]


def test_a_line_with_text_and_usage_gives_both() -> None:
    payload: dict[str, JsonValue] = {
        "choices": [{"delta": {"content": "hi"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }

    assert chunk_sent(payload) == Chunk(
        text="hi", tool_deltas=(), usage=Usage(input_tokens=7, output_tokens=2), error=None
    )


def test_a_line_whose_error_is_truthy_carries_its_data_and_nothing_else() -> None:
    payload: dict[str, JsonValue] = {
        "error": {"message": "overloaded"},
        "choices": [{"delta": {"content": "hi", "tool_calls": [{"index": 0, "id": "a"}]}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }
    data = json.dumps(payload)

    assert chunk_of(payload, data) == Chunk(text="", tool_deltas=(), usage=None, error=data)


@pytest.mark.parametrize("error", [None, "", {}])
def test_a_falsy_error_is_not_a_failure(error: JsonValue) -> None:
    chunk = chunk_sent({"error": error, "choices": [{"delta": {"content": "ok"}}]})

    assert chunk == Chunk(text="ok", tool_deltas=(), usage=None, error=None)


def test_a_choice_that_is_not_an_object_gives_an_empty_chunk() -> None:
    assert chunk_sent({"choices": [5]}) == EMPTY


def test_piece_fields_of_the_wrong_type_are_read_as_absent() -> None:
    piece: dict[str, JsonValue] = {"index": "0", "id": 5, "function": "t", "extra_content": "sig"}

    chunk = chunk_sent({"choices": [{"delta": {"tool_calls": [piece]}}]})

    assert chunk.tool_deltas == (
        ToolDelta(index=None, id=None, name=None, arguments=None, extra_content=None),
    )


def test_an_item_in_tool_calls_that_is_not_an_object_is_skipped() -> None:
    piece: dict[str, JsonValue] = {
        "index": 0,
        "id": "a",
        "function": {"name": "t", "arguments": "{}"},
        "extra_content": {"sig": "s"},
    }

    chunk = chunk_sent({"choices": [{"delta": {"tool_calls": [5, piece]}}]})

    assert chunk.tool_deltas == (
        ToolDelta(index=0, id="a", name="t", arguments="{}", extra_content={"sig": "s"}),
    )
