"""The provider-neutral model seam.

`LLMClient` is what the loop depends on. Concrete providers live under
`adapters/` and nothing outside this package imports one — swapping a provider is
a change in the composition root, not in the loop.

An ABC rather than a `Protocol` because there is one method and every
implementation genuinely subclasses it; a Protocol earns its keep where the
implementations are *not* ours to change (see `tools.ToolLike` in phase 2, which
has to admit MCP-backed tools).
"""

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
        """Stream one model call.

        Implementations MUST yield exactly one terminal event (`Completed` or
        `Failed`) at the end of the stream, including on transport failure. A
        stream that ends without one hangs the caller, which is why the loop
        treats a missing terminal as a failure of its own rather than waiting.

        `tools` offers the model a set of calls it may request. An adapter is
        free to omit the field entirely when it is empty or `None` — an empty
        list says something different from "no tools available", and some
        providers reject it.

        Not `async def`: the return type is the async iterator itself, so an
        implementation is an `async def` generator and a caller may `aclose()`
        it. Making this `async` would put a coroutine in front of the generator
        and break that.
        """
