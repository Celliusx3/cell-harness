"""The `LLMClient` protocol every adapter satisfies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from harness.llm.messages import Message, ToolSpec
from harness.llm.stream import StreamEvent


class LLMClient(ABC):
    """Streams a completion event by event."""

    @abstractmethod
    def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream one model call."""
