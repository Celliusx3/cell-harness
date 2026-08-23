"""Test doubles for the LLM seam.

A fake client is the whole reason `LLMClient` is a seam: the loop's behaviour on
a dropped stream, a missing terminal, or a cancellation is not reproducible
against a real provider, and every one of those is a contract the loop owes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from harness.llm.client import LLMClient
from harness.llm.messages import Message
from harness.llm.stream import Completed, StreamEvent, TextChunk


class ScriptedClient(LLMClient):
    """Yields a fixed script, recording what it was asked.

    `seen` is the last request's messages — how a test asserts that history came
    from the log rather than from somewhere the loop kept it.
    """

    def __init__(self, script: Sequence[StreamEvent]) -> None:
        self._script = list(script)
        self.seen: list[Message] = []
        self.calls = 0

    async def stream_completion(
        self, messages: list[Message], model: str
    ) -> AsyncIterator[StreamEvent]:
        self.seen = list(messages)
        self.calls += 1
        for event in self._script:
            yield event


class HangingClient(LLMClient):
    """Streams `text`, then blocks forever.

    Stands in for a turn the user cancels mid-reply: there is a visible prefix
    and no terminal event, which is the state the loop must finalize.

    Note there is nothing to await *before* the block — a generator suspended at
    a `yield` does not run another line until its consumer asks for the next
    item, so a "started" flag set after the yield could never be observed by a
    consumer that stops there. Closing the generator is the whole event.
    """

    def __init__(self, text: str) -> None:
        self._text = text
        self.closed = False

    async def stream_completion(
        self, messages: list[Message], model: str
    ) -> AsyncIterator[StreamEvent]:
        try:
            yield TextChunk(text=self._text)
            await asyncio.Event().wait()  # never set
        finally:
            # Set only if the caller closed us properly. `test_cancel` asserts
            # it, which is what proves the loop's `aclosing` is doing its job
            # rather than leaving the adapter to the garbage collector.
            self.closed = True


def completed(text: str) -> list[StreamEvent]:
    """The ordinary script: stream `text` in one chunk, then finish."""
    return [TextChunk(text=text), Completed(full_text=text)]
