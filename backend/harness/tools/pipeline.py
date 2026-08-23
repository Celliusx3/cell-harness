"""Dispatch: find the tool a call names, and run it.

A thin layer, but not a pointless one — the registry lookup and the unknown-tool
failure need a home that is not the loop, so the loop can stay about turns and
steps.

Unknown tools are a `Failure`, not an exception: a model that hallucinates a name
should be told so and given another step, not have the turn die.

**Where interception will go.** Phase 8 needs a timeout and the loop guardrail to
wrap every call, and phase 12 needs an approval gate. Those become an
around-middleware chain here — a listener that awaits the inner call can time it,
and one that returns without awaiting refuses it. That chain does not exist yet
because nothing registers into it; adding it changes this method's body and
nothing else, so there is no reason to build it before its first listener.
"""

from __future__ import annotations

from harness.llm.messages import ToolCall, ToolSpec
from harness.tools.definition import UNKNOWN_TOOL, Failure, ToolOutcome
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolRegistry


class ToolPipeline:
    """Resolves and runs the tool a call names."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def specs(self) -> list[ToolSpec]:
        """What the model is offered this step.

        Delegated rather than reached through a `registry` attribute, so the loop
        depends on the pipeline alone — a composition that swaps in a different
        dispatcher (a remote one) does not have to expose a registry it may not
        have.
        """
        return self._registry.specs()

    async def execute(self, call: ToolCall, *, progress: ToolProgressReporter) -> ToolOutcome:
        """Run one call."""
        tool = self._registry.get(call.name)
        if tool is None:
            # Naming what *is* available turns a dead end into a correction the
            # model can act on next step, which is the whole reason an unknown
            # tool is a Failure rather than an exception.
            available = ", ".join(sorted(t.name for t in self._registry.all())) or "none"
            return Failure(
                UNKNOWN_TOOL,
                f"tool {call.name!r} is not available. Available tools: {available}",
            )
        return await tool.invoke(call.arguments, progress=progress)
