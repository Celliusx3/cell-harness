"""Tool calls that stream in pieces, joined back into whole calls."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace

from harness.llm.adapters.openai.models.tool_delta import ToolDelta
from harness.llm.models.tools import ExtraContent, ToolCall

logger = logging.getLogger("harness.llm.openai")


@dataclass(frozen=True)
class _PartialCall:
    """What the deltas of one call have said so far."""

    id: str | None = None
    name: str = ""
    arguments: str = ""
    extra_content: ExtraContent | None = None


def _with_delta(call: _PartialCall, delta: ToolDelta) -> _PartialCall:
    """`call` with what `delta` adds: its id, its name, more arguments, its extra content."""
    return replace(
        call,
        id=delta.id if delta.id is not None else call.id,
        name=delta.name if delta.name is not None else call.name,
        arguments=(
            call.arguments + delta.arguments if delta.arguments is not None else call.arguments
        ),
        extra_content=(
            delta.extra_content if delta.extra_content is not None else call.extra_content
        ),
    )


class ToolCallAssembler:
    """Joins the deltas of each call a reply streams."""

    def __init__(self) -> None:
        self._calls: dict[int, _PartialCall] = {}
        self._index_by_id: dict[str, int] = {}

    def _index_of(self, delta: ToolDelta) -> int:
        """The delta's own index, or for a call sent without one, the next free one per id."""
        if delta.index is not None:
            return delta.index
        if delta.id is not None and delta.id in self._index_by_id:
            return self._index_by_id[delta.id]
        index = max(self._calls, default=-1) + 1
        if delta.id is not None:
            self._index_by_id[delta.id] = index
        return index

    def add(self, deltas: Sequence[ToolDelta]) -> None:
        """Join each tool delta to the call it belongs to."""
        for delta in deltas:
            index = self._index_of(delta)
            self._calls[index] = _with_delta(self._calls.get(index, _PartialCall()), delta)

    def tool_calls(self) -> list[ToolCall]:
        """Every assembled call, in the index order the provider used."""
        calls = []
        for index in sorted(self._calls):
            call = self._calls[index]
            if not call.name:
                logger.warning("dropping tool call fragment with no name: %r", call)
                continue
            calls.append(
                ToolCall(
                    id=call.id or f"call_{index}",
                    name=call.name,
                    arguments=call.arguments,
                    extra_content=call.extra_content,
                )
            )
        return calls
