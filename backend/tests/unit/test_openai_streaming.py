"""One streamed line read into a chunk: each field kept only when it has the type it should."""

from __future__ import annotations

import pytest
from pydantic import JsonValue

from harness.llm import Usage
from harness.llm.adapters.openai._streaming import chunk_of
from harness.llm.adapters.openai.models.chunk import Chunk
from harness.llm.adapters.openai.models.tool_delta import ToolDelta

EMPTY = Chunk(text="", tool_deltas=(), usage=None, failed=False)


def test_a_line_with_text_and_usage_gives_both() -> None:
    payload: dict[str, JsonValue] = {
        "choices": [{"delta": {"content": "hi"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }

    assert chunk_of(payload) == Chunk(
        text="hi", tool_deltas=(), usage=Usage(input_tokens=7, output_tokens=2), failed=False
    )


def test_a_line_whose_error_is_truthy_is_failed_and_carries_nothing_else() -> None:
    payload: dict[str, JsonValue] = {
        "error": {"message": "overloaded"},
        "choices": [{"delta": {"content": "hi", "tool_calls": [{"index": 0, "id": "a"}]}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }

    assert chunk_of(payload) == Chunk(text="", tool_deltas=(), usage=None, failed=True)


@pytest.mark.parametrize("error", [None, "", {}])
def test_a_falsy_error_is_not_a_failure(error: JsonValue) -> None:
    chunk = chunk_of({"error": error, "choices": [{"delta": {"content": "ok"}}]})

    assert chunk == Chunk(text="ok", tool_deltas=(), usage=None, failed=False)


def test_a_choice_that_is_not_an_object_gives_an_empty_chunk() -> None:
    assert chunk_of({"choices": [5]}) == EMPTY


def test_piece_fields_of_the_wrong_type_are_read_as_absent() -> None:
    piece: dict[str, JsonValue] = {"index": "0", "id": 5, "function": "t", "extra_content": "sig"}

    chunk = chunk_of({"choices": [{"delta": {"tool_calls": [piece]}}]})

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

    chunk = chunk_of({"choices": [{"delta": {"tool_calls": [5, piece]}}]})

    assert chunk.tool_deltas == (
        ToolDelta(index=0, id="a", name="t", arguments="{}", extra_content={"sig": "s"}),
    )
