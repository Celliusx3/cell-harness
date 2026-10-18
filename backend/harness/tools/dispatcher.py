"""Find the tool a call names, and run it."""

from __future__ import annotations

from harness.llm import ToolCall
from harness.tools.approval import ApprovalGate
from harness.tools.models.context import CallOrigin, ToolContext, ToolProgressReporter
from harness.tools.models.outcome import UNKNOWN_TOOL, Failure, Pending, ToolOutcome
from harness.tools.registry import ToolRegistry


class ToolDispatcher:
    """Runs the tool a call names, whoever made the call."""

    def __init__(self, registry: ToolRegistry, gate: ApprovalGate) -> None:
        self._registry = registry
        self._gate = gate

    async def dispatch(
        self,
        call: ToolCall,
        *,
        progress: ToolProgressReporter,
        approved: bool,
        origin: CallOrigin,
    ) -> ToolOutcome:
        """Run one call, whether the model made it or a script did — unless it must ask first."""
        if not approved and self._gate.should_ask(call.name):
            return Pending()
        tool = self._registry.get(call.name)
        if tool is None:
            return Failure(UNKNOWN_TOOL, self._unknown_tool_message(call.name))
        context = ToolContext(call_id=call.id, progress=progress, origin=origin)
        return await tool.invoke(call.arguments, context=context)

    def _unknown_tool_message(self, name: str) -> str:
        """The failure text for a name nobody registered, naming what is available."""
        available = ", ".join(sorted(t.name for t in self._registry.all())) or "none"
        return f"tool {name!r} is not available. Available tools: {available}"
