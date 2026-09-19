"""Test doubles for the LLM seam and for tools."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from pydantic import BaseModel, Field

from harness.llm.client import LLMClient
from harness.llm.messages import Message, ToolCall, ToolSpec
from harness.llm.stream import Completed, StreamEvent, TextChunk, ToolCallChunk
from harness.tools.context import ToolContext
from harness.tools.definition import Ok, Pending, ToolDefinition, ToolOutcome


class ScriptedClient(LLMClient):
    """Yields a fixed script, recording what it was asked."""

    def __init__(self, script: Sequence[StreamEvent]) -> None:
        self._script = list(script)
        self.seen: list[Message] = []
        self.seen_tools: list[ToolSpec] | None = None
        self.calls = 0

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        self.seen = list(messages)
        self.seen_tools = tools
        self.calls += 1
        for event in self._script:
            yield event


class SteppedClient(LLMClient):
    """Yields a different script per call — one per step of a turn."""

    def __init__(self, *scripts: Sequence[StreamEvent]) -> None:
        self._scripts = [list(s) for s in scripts]
        self.seen: list[Message] = []
        self.seen_per_call: list[list[Message]] = []
        self.seen_tools: list[ToolSpec] | None = None
        self.seen_tools_per_call: list[list[ToolSpec] | None] = []
        self.calls = 0

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        self.seen = list(messages)
        self.seen_per_call.append(list(messages))
        self.seen_tools = tools
        self.seen_tools_per_call.append(list(tools) if tools is not None else None)
        script = self._scripts[min(self.calls, len(self._scripts) - 1)]
        self.calls += 1
        for event in script:
            yield event


class HangingClient(LLMClient):
    """Streams `text`, then blocks forever."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.closed = False

    async def stream_completion(
        self, messages: list[Message], model: str, *, tools: list[ToolSpec] | None = None
    ) -> AsyncIterator[StreamEvent]:
        try:
            yield TextChunk(text=self._text)
            await asyncio.Event().wait()
        finally:
            self.closed = True


def completed(text: str) -> list[StreamEvent]:
    """The ordinary script: stream `text` in one chunk, then finish."""
    return [TextChunk(text=text), Completed(full_text=text)]


def calls_tool(
    name: str, arguments: str = "{}", *, text: str = "", id: str = "c1"
) -> list[StreamEvent]:
    """A script whose step asks for one tool call."""
    call = ToolCall(id=id, name=name, arguments=arguments)
    events: list[StreamEvent] = [TextChunk(text=text)] if text else []
    return [
        *events,
        ToolCallChunk(call=call),
        Completed(full_text=text, tool_calls=(call,)),
    ]


class EchoArgs(BaseModel):
    """Arguments for the `echo` fake tool."""

    value: str = Field(description="Text to echo back.")


def echo_tool(name: str = "echo") -> ToolDefinition[EchoArgs]:
    """A tool that succeeds, for testing dispatch and schema derivation."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        return Ok(content=args.value)

    return ToolDefinition.from_model(
        name=name, description="Echo the value back.", args_model=EchoArgs, execute=execute
    )


def reporting_tool(reports: Sequence[tuple[float | None, str]]) -> ToolDefinition[EchoArgs]:
    """A tool that reports progress before returning."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        for percent, message in reports:
            await context.progress(percent=percent, message=message)
        return Ok(content=args.value)

    return ToolDefinition.from_model(
        name="slow", description="Reports progress.", args_model=EchoArgs, execute=execute
    )


def hanging_tool(name: str = "hang") -> ToolDefinition[EchoArgs]:
    """A tool that never returns."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    return ToolDefinition.from_model(
        name=name, description="Never returns.", args_model=EchoArgs, execute=execute
    )


def gated_tool(release: asyncio.Event, name: str = "gate") -> ToolDefinition[EchoArgs]:
    """A tool that returns once the test says so."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        await release.wait()
        return Ok(content=args.value)

    return ToolDefinition.from_model(
        name=name, description="Returns when released.", args_model=EchoArgs, execute=execute
    )


def raising_tool(name: str = "boom") -> ToolDefinition[EchoArgs]:
    """A tool whose body blows up — a bug in a tool must not kill the turn."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        raise RuntimeError("kaboom")

    return ToolDefinition.from_model(
        name=name, description="Always raises.", args_model=EchoArgs, execute=execute
    )


def pending_tool(name: str = "ask") -> ToolDefinition[EchoArgs]:
    """A client tool: it does not compute, it says the person will."""

    async def execute(args: EchoArgs, context: ToolContext) -> ToolOutcome:
        return Pending()

    return ToolDefinition.from_model(
        name=name, description="The person answers.", args_model=EchoArgs, execute=execute
    )
