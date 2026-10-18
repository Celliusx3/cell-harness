"""The `LLMClient` base class every adapter implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from harness.llm.models.messages import Message
from harness.llm.models.stream import StreamEvent
from harness.llm.models.tools import ToolSpec


class LLMClient(ABC):
    """Streams a completion event by event."""

    @abstractmethod
    def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None
    ) -> AsyncIterator[StreamEvent]:
        """Stream one model call."""
