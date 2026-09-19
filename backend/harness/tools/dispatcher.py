"""Find the tool a call names, and run it."""

from __future__ import annotations

from harness.llm.messages import ToolCall
from harness.tools.context import ToolContext
from harness.tools.definition import UNKNOWN_TOOL, Failure, ToolOutcome
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolRegistry


class ToolDispatcher:
    """Runs the tool a call names, whoever made the call."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def dispatch(self, call: ToolCall, *, progress: ToolProgressReporter) -> ToolOutcome:
        """Run one call, whether the model made it or a script did."""
        tool = self._registry.get(call.name)
        if tool is None:
            return Failure(UNKNOWN_TOOL, self._unknown(call.name))
        context = ToolContext(call_id=call.id, progress=progress)
        return await tool.invoke(call.arguments, context=context)

    def _unknown(self, name: str) -> str:
        """The failure text for a name nobody registered, naming what is available."""
        available = ", ".join(sorted(t.name for t in self._registry.all())) or "none"
        return f"tool {name!r} is not available. Available tools: {available}"
