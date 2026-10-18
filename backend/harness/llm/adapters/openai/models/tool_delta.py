"""One tool call fragment, as a streamed line carries it."""

from __future__ import annotations

from dataclasses import dataclass

from harness.llm.models.tools import ExtraContent


@dataclass(frozen=True)
class ToolDelta:
    """What one tool call fragment said, `None` where it said nothing usable."""

    index: int | None
    id: str | None
    name: str | None
    arguments: str | None
    extra_content: ExtraContent | None
