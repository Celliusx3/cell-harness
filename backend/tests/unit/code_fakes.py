"""A fake sandbox and a recording dispatcher for the code-mode tools."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from harness.llm.messages import ToolCall
from harness.sandbox import Bridge, DenoUnavailableError, Runner, Script
from harness.tools.approval import ApprovalGate
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.native.code import code_mode_tools
from harness.tools.registry import ToolRegistry
from tests.unit.helpers import context_for, no_gate


def returns(outcome: Ok):
    async def run(args, progress):
        return outcome

    return run


def tool(name: str, description: str = "A tool.", schema: object | None = None) -> ToolDefinition:
    async def run(args, progress):
        return Ok(f"{name} ran", data={"rows": [1, 2]})

    return ToolDefinition(
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


class RecordingDispatcher(ToolDispatcher):
    """A real dispatcher that remembers what it was asked to run."""

    def __init__(self, registry: ToolRegistry, gate: ApprovalGate) -> None:
        super().__init__(registry, gate)
        self.calls: list[ToolCall] = []

    async def dispatch(self, call: ToolCall, *, progress, approved: bool) -> ToolOutcome:
        self.calls.append(call)
        return await super().dispatch(call, progress=progress, approved=approved)


@dataclass
class Built:
    """The three tools, the registry behind them, and what the dispatcher saw."""

    tools: list[ToolDefinition]
    registry: ToolRegistry
    dispatcher: RecordingDispatcher

    @property
    def dispatched(self) -> list[ToolCall]:
        return self.dispatcher.calls

    def tool(self, name: str) -> ToolDefinition:
        return next(t for t in self.tools if t.name == name)

    async def run(self, name: str, arguments: str = "{}") -> ToolOutcome:
        return await self.tool(name).invoke(arguments, context=context_for())


def build(
    *tools: ToolDefinition,
    runtime: FakeRunner | None = None,
    withheld: frozenset[str] = frozenset(),
    gate: ApprovalGate | None = None,
) -> Built:
    registry = ToolRegistry(tools)
    dispatcher = RecordingDispatcher(registry, gate or no_gate())
    built = code_mode_tools(
        registry=registry, dispatcher=dispatcher, runtime=runtime or FakeRunner(), withheld=withheld
    )
    return Built(tools=built, registry=registry, dispatcher=dispatcher)
