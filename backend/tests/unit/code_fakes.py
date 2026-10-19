"""A fake sandbox and a recording dispatcher for the code-mode tools."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from harness.llm import ToolCall
from harness.sandbox import Bridge, DenoUnavailableError, Runner, Script
from harness.tools import (
    Approvals,
    CallOrigin,
    Ok,
    Tool,
    ToolOutcome,
    ToolService,
)
from harness.tools.native.code_mode import code_mode_tools
from tests.unit.helpers import context_for, no_approvals


def returns(outcome: Ok):
    async def run(args, progress):
        return outcome

    return run


def tool(name: str, description: str = "A tool.", schema: object | None = None) -> Tool:
    async def run(args, progress):
        return Ok(f"{name} ran", data={"rows": [1, 2]})

    return Tool(
        name=name,
        description=description,
        input_schema=schema or {"type": "object", "properties": {"url": {"type": "string"}}},
        parse=lambda raw: raw,
        execute=run,
    )


@dataclass
class FakeRunner(Runner):
    """Stands in for Deno."""

    script: Callable[[Bridge], object] | None = None
    outcome: Script = field(default_factory=lambda: Script(result="ok"))
    unavailable: bool = False
    seen_names: list[str] = field(default_factory=list)
    seen_code: str = ""

    async def run(self, code: str, *, names: Sequence[str], bridge: Bridge) -> Script:
        if self.unavailable:
            raise DenoUnavailableError("no deno here")
        self.seen_names = list(names)
        self.seen_code = code
        if self.script is not None:
            await self.script(bridge)
        return self.outcome


class RecordingToolService(ToolService):
    """A real tool service that remembers what it was asked to run."""

    def __init__(self, tools: tuple[Tool, ...], approvals: Approvals) -> None:
        super().__init__(tools, approvals=approvals)
        self.calls: list[ToolCall] = []

    async def dispatch(
        self, call: ToolCall, *, progress, approved: bool, origin: CallOrigin
    ) -> ToolOutcome:
        self.calls.append(call)
        return await super().dispatch(call, progress=progress, approved=approved, origin=origin)


@dataclass
class Built:
    """The three tools, and the tool service behind them that remembers what it ran."""

    tools: list[Tool]
    tool_service: RecordingToolService

    @property
    def dispatched(self) -> list[ToolCall]:
        return self.tool_service.calls

    def tool(self, name: str) -> Tool:
        return next(t for t in self.tools if t.name == name)

    async def run(self, name: str, arguments: str = "{}") -> ToolOutcome:
        return await self.tool(name).invoke(arguments, context=context_for())


def build(
    *tools: Tool,
    runner: FakeRunner | None = None,
    withheld: frozenset[str] = frozenset(),
    approvals: Approvals | None = None,
) -> Built:
    tool_service = RecordingToolService(tools, approvals or no_approvals())
    built = code_mode_tools(
        tool_service=tool_service, runner=runner or FakeRunner(), withheld=withheld
    )
    return Built(tools=built, tool_service=tool_service)
