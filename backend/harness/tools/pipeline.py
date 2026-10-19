"""What the model is offered — and, for its own calls, what it may run."""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm import ToolCall, ToolSpec
from harness.tools.models.context import CallOrigin, ToolProgressReporter
from harness.tools.models.outcome import REFUSED, Failure, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.service import ToolService

MAX_TOOLS_SELECTED = 8


class ToolPipeline:
    """The tool list one step is built from."""

    def __init__(self, tool_service: ToolService, default_tools: Sequence[str]) -> None:
        self.tool_service = tool_service
        self._default = tuple(default_tools)

    def specs(self, tools_selected: Sequence[str] = ()) -> list[ToolSpec]:
        """What the model is offered this step — the only place visibility is decided."""
        return [tool.spec() for tool in self._offered_tools(tools_selected)]

    def _offered_tools(self, tools_selected: Sequence[str]) -> list[Tool]:
        by_name = {t.name: t for t in self.tool_service.all()}
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
        origin: CallOrigin,
        tools_selected: Sequence[str] = (),
    ) -> ToolOutcome:
        """Run one of the model's own calls — if it was offered."""
        if call.name not in {tool.name for tool in self._offered_tools(tools_selected)}:
            return Failure(REFUSED, _not_offered_message(call.name))
        return await self.tool_service.dispatch(
            call, progress=progress, approved=False, origin=origin
        )

    async def execute_approved(
        self, call: ToolCall, *, progress: ToolProgressReporter, origin: CallOrigin
    ) -> ToolOutcome:
        """Run a call the person has approved — they opened this door, so no offered check."""
        return await self.tool_service.dispatch(
            call, progress=progress, approved=True, origin=origin
        )


def _not_offered_message(name: str) -> str:
    return (
        f"{name!r} is not in your tool list. Select it by reading its schema with "
        "get_function_details — then it is, and you can call it directly. "
        "See list_functions for what exists."
    )
