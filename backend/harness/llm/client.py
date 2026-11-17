"""The `LLMClient` every adapter is: one model call, streamed event by event."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from harness.llm.domain.messages import Message
from harness.llm.domain.stream import StreamEvent
from harness.llm.domain.tools import ToolSpec


class LLMClient(Protocol):
    """Streams a completion event by event."""

    def stream_completion(
        self, messages: list[Message], *, tools: list[ToolSpec] | None
    ) -> AsyncIterator[StreamEvent]:
        """Stream one call to the model this client is set up for."""
        ...
