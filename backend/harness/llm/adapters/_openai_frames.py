"""One streamed Chat Completions line, read once into a typed frame."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import JsonValue, TypeAdapter, ValidationError

from harness.llm.models.stream import Usage
from harness.llm.models.tools import ExtraContent

logger = logging.getLogger("harness.llm.openai")

_EXTRA_CONTENT = TypeAdapter(ExtraContent)


@dataclass(frozen=True)
class CallPiece:
    """What one tool call fragment said, `None` where it said nothing usable."""

    index: int | None
    id: str | None
    name: str | None
    arguments: str | None
    extra_content: ExtraContent | None


@dataclass(frozen=True)
class Frame:
    """What one line adds: its text, its tool call pieces, its token count, whether it failed."""

    text: str
    pieces: tuple[CallPiece, ...]
    usage: Usage | None
    failed: bool


def frame_of(payload: dict[str, JsonValue]) -> Frame:
    """The frame one parsed line says, each field left out when it is not the type it should be."""
    if payload.get("error"):
        return Frame(text="", pieces=(), usage=None, failed=True)
    delta = _delta(payload)
    content = delta.get("content")
    return Frame(
        text=content if isinstance(content, str) else "",
        pieces=_pieces(delta),
        usage=_usage(payload),
        failed=False,
    )


def _usage(payload: Mapping[str, JsonValue]) -> Usage | None:
    """Token accounting from a line that carries it, or `None`."""
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, int) or not isinstance(completion, int):
        return None
    return Usage(input_tokens=prompt, output_tokens=completion)


def _delta(payload: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    """The `delta` object of the line's first choice, or `{}`."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return {}
    choice = choices[0]
    delta = choice.get("delta") if isinstance(choice, dict) else None
    return delta if isinstance(delta, dict) else {}


def _pieces(delta: Mapping[str, JsonValue]) -> tuple[CallPiece, ...]:
    """Each tool call fragment in `delta` that is an object."""
    pieces = delta.get("tool_calls")
    if not isinstance(pieces, list):
        return ()
    return tuple(_piece(piece) for piece in pieces if isinstance(piece, dict))


def _piece(piece: Mapping[str, JsonValue]) -> CallPiece:
    """One fragment, each field kept only when it has the type the wire promises."""
    function = piece.get("function")
    fields = function if isinstance(function, dict) else {}
    index, call_id = piece.get("index"), piece.get("id")
    name, arguments = fields.get("name"), fields.get("arguments")
    return CallPiece(
        index=index if isinstance(index, int) else None,
        id=call_id if isinstance(call_id, str) else None,
        name=name if isinstance(name, str) else None,
        arguments=arguments if isinstance(arguments, str) else None,
        extra_content=_extra_content(piece),
    )


def _extra_content(piece: Mapping[str, JsonValue]) -> ExtraContent | None:
    """The piece's `extra_content`, such as Gemini's thought signature, when it is an object."""
    raw = piece.get("extra_content")
    if raw is None:
        return None
    try:
        return _EXTRA_CONTENT.validate_python(raw)
    except ValidationError:
        logger.warning("dropped a tool call's extra_content that is not an object: %r", raw)
        return None
