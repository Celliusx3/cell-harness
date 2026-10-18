"""Tool calls that stream in pieces, joined back into whole calls."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace

from pydantic import JsonValue, TypeAdapter, ValidationError

from harness.llm.messages import ExtraContent, ToolCall

logger = logging.getLogger("harness.llm.openai")

_EXTRA_CONTENT = TypeAdapter(ExtraContent)


@dataclass(frozen=True)
class _PartialCall:
    """What the pieces of one call have said so far."""

    id: str | None = None
    name: str = ""
    arguments: str = ""
    extra_content: ExtraContent | None = None


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


def _joined(call: _PartialCall, piece: Mapping[str, JsonValue]) -> _PartialCall:
    """`call` with what `piece` adds: its id, its name, more arguments, its extra content."""
    function = piece.get("function")
    fields = function if isinstance(function, dict) else {}
    piece_id, name, arguments = piece.get("id"), fields.get("name"), fields.get("arguments")
    extra = _extra_content(piece)
    return replace(
        call,
        id=piece_id if isinstance(piece_id, str) else call.id,
        name=name if isinstance(name, str) else call.name,
        arguments=call.arguments + arguments if isinstance(arguments, str) else call.arguments,
        extra_content=extra if extra is not None else call.extra_content,
    )


class ToolCallAccumulator:
    """Joins the pieces of each call a reply streams."""

    def __init__(self) -> None:
        self._by_slot: dict[int, _PartialCall] = {}
        self._slot_of_unindexed_id: dict[str, int] = {}

    def _slot(self, piece: Mapping[str, JsonValue]) -> int:
        """The piece's own index, or for a call sent without one, the next free one per id."""
        index = piece.get("index")
        if isinstance(index, int):
            return index
        call_id = piece.get("id")
        if isinstance(call_id, str) and call_id in self._slot_of_unindexed_id:
            return self._slot_of_unindexed_id[call_id]
        slot = max(self._by_slot, default=-1) + 1
        if isinstance(call_id, str):
            self._slot_of_unindexed_id[call_id] = slot
        return slot

    def add(self, delta: Mapping[str, JsonValue]) -> None:
        """Join each tool call piece in `delta` to the call it belongs to."""
        pieces = delta.get("tool_calls")
        if not isinstance(pieces, list):
            return
        for piece in pieces:
            if not isinstance(piece, dict):
                continue
            slot = self._slot(piece)
            self._by_slot[slot] = _joined(self._by_slot.get(slot, _PartialCall()), piece)

    def tool_calls(self) -> list[ToolCall]:
        """Every assembled call, in the index order the provider used."""
        calls = []
        for slot in sorted(self._by_slot):
            call = self._by_slot[slot]
            if not call.name:
                logger.warning("dropping tool call fragment with no name: %r", call)
                continue
            calls.append(
                ToolCall(
                    id=call.id or f"call_{slot}",
                    name=call.name,
                    arguments=call.arguments,
                    extra_content=call.extra_content,
                )
            )
        return calls
