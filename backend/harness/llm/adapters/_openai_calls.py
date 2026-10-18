"""Tool calls that stream in pieces, joined back into whole calls."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace

from harness.llm.adapters._openai_frames import CallPiece
from harness.llm.messages import ExtraContent, ToolCall

logger = logging.getLogger("harness.llm.openai")


@dataclass(frozen=True)
class _PartialCall:
    """What the pieces of one call have said so far."""

    id: str | None = None
    name: str = ""
    arguments: str = ""
    extra_content: ExtraContent | None = None


def _joined(call: _PartialCall, piece: CallPiece) -> _PartialCall:
    """`call` with what `piece` adds: its id, its name, more arguments, its extra content."""
    return replace(
        call,
        id=piece.id if piece.id is not None else call.id,
        name=piece.name if piece.name is not None else call.name,
        arguments=(
            call.arguments + piece.arguments if piece.arguments is not None else call.arguments
        ),
        extra_content=(
            piece.extra_content if piece.extra_content is not None else call.extra_content
        ),
    )


class ToolCallAccumulator:
    """Joins the pieces of each call a reply streams."""

    def __init__(self) -> None:
        self._by_slot: dict[int, _PartialCall] = {}
        self._slot_of_unindexed_id: dict[str, int] = {}

    def _slot(self, piece: CallPiece) -> int:
        """The piece's own index, or for a call sent without one, the next free one per id."""
        if piece.index is not None:
            return piece.index
        if piece.id is not None and piece.id in self._slot_of_unindexed_id:
            return self._slot_of_unindexed_id[piece.id]
        slot = max(self._by_slot, default=-1) + 1
        if piece.id is not None:
            self._slot_of_unindexed_id[piece.id] = slot
        return slot

    def add(self, pieces: Sequence[CallPiece]) -> None:
        """Join each tool call piece to the call it belongs to."""
        for piece in pieces:
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
