"""One streamed line, read once into a typed chunk."""

from __future__ import annotations

from dataclasses import dataclass

from harness.llm.adapters.openai.models.tool_delta import ToolDelta
from harness.llm.models.stream import Usage


@dataclass(frozen=True)
class Chunk:
    """What one line adds: its text, its tool deltas, its token count, whether it failed."""

    text: str
    tool_deltas: tuple[ToolDelta, ...]
    usage: Usage | None
    failed: bool
