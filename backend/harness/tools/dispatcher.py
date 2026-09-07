"""Find the tool a call names, and run it.

A thin layer, but not a pointless one — the registry lookup and the unknown-tool
failure need a home that is not the loop, so the loop can stay about turns and
steps.

Unknown tools are a `Failure`, not an exception: a caller that hallucinates a
name should be told so and given another step, not have the turn die.

**Where interception will go.** Phase 8 needs a timeout and the loop guardrail to
wrap every call, and phase 12 needs an approval gate. Those become an
around-middleware chain here — a listener that awaits the inner call can time it,
and one that returns without awaiting refuses it. That chain does not exist yet
because nothing registers into it; adding it changes `dispatch`'s body and
nothing else, so there is no reason to build it before its first listener.

**This is the one door.** Code mode calls `dispatch` once per tool a script uses,
so anything added to that chain covers scripts without knowing they exist. Two
dispatchers would let a gate be installed on one and not the other, with nothing
in the types or the tests to say which path was covered.
"""

from __future__ import annotations

from harness.llm.messages import ToolCall
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
        return await tool.invoke(call.arguments, progress=progress)

    def _unknown(self, name: str) -> str:
        """Naming what *is* available turns a dead end into a correction the
        caller can act on next step, which is the whole reason an unknown tool is
        a Failure rather than an exception.
        """
        available = ", ".join(sorted(t.name for t in self._registry.all())) or "none"
        return f"tool {name!r} is not available. Available tools: {available}"
