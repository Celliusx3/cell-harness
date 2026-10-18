"""One streamed line read into a frame: each field kept only when it has the type it should."""

from __future__ import annotations

import pytest
from pydantic import JsonValue

from harness.llm.adapters._openai_frames import CallPiece, Frame, frame_of
from harness.llm.stream import Usage

EMPTY = Frame(text="", pieces=(), usage=None, failed=False)


def test_a_line_with_text_and_usage_gives_both() -> None:
    payload: dict[str, JsonValue] = {
        "choices": [{"delta": {"content": "hi"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }

    assert frame_of(payload) == Frame(
        text="hi", pieces=(), usage=Usage(input_tokens=7, output_tokens=2), failed=False
    )


def test_a_line_whose_error_is_truthy_is_failed_and_carries_nothing_else() -> None:
    payload: dict[str, JsonValue] = {
        "error": {"message": "overloaded"},
        "choices": [{"delta": {"content": "hi", "tool_calls": [{"index": 0, "id": "a"}]}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }

    assert frame_of(payload) == Frame(text="", pieces=(), usage=None, failed=True)


@pytest.mark.parametrize("error", [None, "", {}])
def test_a_falsy_error_is_not_a_failure(error: JsonValue) -> None:
    frame = frame_of({"error": error, "choices": [{"delta": {"content": "ok"}}]})

    assert frame == Frame(text="ok", pieces=(), usage=None, failed=False)


def test_a_choice_that_is_not_an_object_gives_an_empty_frame() -> None:
    assert frame_of({"choices": [5]}) == EMPTY


def test_piece_fields_of_the_wrong_type_are_read_as_absent() -> None:
    piece: dict[str, JsonValue] = {"index": "0", "id": 5, "function": "t", "extra_content": "sig"}

    frame = frame_of({"choices": [{"delta": {"tool_calls": [piece]}}]})

    assert frame.pieces == (
        CallPiece(index=None, id=None, name=None, arguments=None, extra_content=None),
    )


def test_an_item_in_tool_calls_that_is_not_an_object_is_skipped() -> None:
    piece: dict[str, JsonValue] = {
        "index": 0,
        "id": "a",
        "function": {"name": "t", "arguments": "{}"},
        "extra_content": {"sig": "s"},
    }

    frame = frame_of({"choices": [{"delta": {"tool_calls": [5, piece]}}]})

    assert frame.pieces == (
        CallPiece(index=0, id="a", name="t", arguments="{}", extra_content={"sig": "s"}),
    )
