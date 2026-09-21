"""What the model is offered — and, for its own calls, what it may run."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import ToolCall, ToolSpec
from harness.tools.definition import REFUSED, Failure, ToolDefinition, ToolOutcome
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolRegistry

MAX_TOOLS_SELECTED = 8


class ToolPipeline:
    """The tool list one step is built from."""

    def __init__(
        self,
        registry: ToolRegistry,
        dispatcher: ToolDispatcher,
        default_tools: Sequence[str],
    ) -> None:
        self._registry = registry
        self._dispatcher = dispatcher
        self._default = tuple(default_tools)

    def specs(self, tools_selected: Sequence[str] = ()) -> list[ToolSpec]:
        """What the model is offered this step — the only place visibility is decided."""
        return [tool.spec() for tool in self._offered(tools_selected)]

    def _offered(self, tools_selected: Sequence[str]) -> list[ToolDefinition]:
        by_name = {t.name: t for t in self._registry.all()}
        offered = [by_name[n] for n in self._default if n in by_name]
        chosen = {tool.name for tool in offered}
        recent = tuple(tools_selected)[-MAX_TOOLS_SELECTED:]
        selected = sorted(
            (by_name[n] for n in recent if n in by_name and n not in chosen),
            key=lambda tool: tool.name,
        )
        return [*offered, *selected]

    async def execute(
        self,
        call: ToolCall,
        *,
        progress: ToolProgressReporter,
        tools_selected: Sequence[str] = (),
    ) -> ToolOutcome:
        """Run one of the model's own calls — if it was offered."""
        if call.name not in {tool.name for tool in self._offered(tools_selected)}:
            return Failure(REFUSED, _not_offered(call.name))
        return await self._dispatcher.dispatch(call, progress=progress, approved=False)

    async def approve(self, call: ToolCall, *, progress: ToolProgressReporter) -> ToolOutcome:
        """Run a call the person has approved — they opened this door, so no offered check."""
        return await self._dispatcher.dispatch(call, progress=progress, approved=True)


def _not_offered(name: str) -> str:
    return (
        f"{name!r} is not in your tool list. Select it by reading its schema with "
        "get_function_details — then it is, and you can call it directly. "
        "See list_functions for what exists."
    )
