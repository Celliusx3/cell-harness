"""Find the tool a call names, and run it.

A thin layer, but not a pointless one — the registry lookup and the unknown-tool
failure need a home that is not the loop, so the loop can stay about turns and
steps.

Unknown tools are a `Failure`, not an exception: a caller that hallucinates a
name should be told so and given another step, not have the turn die.

**Where interception did not go.** This was to be the home of an
around-middleware chain — a timeout, the loop guardrail, one day an approval
gate. The guardrail went to the loop instead (`agent/hooks/`), because what
it reads is the session log, which `dispatch` never sees; and the timeout was
never built, because every tool that can hang already bounds itself where it
can be stopped (MCP's command timeout, the sandbox's script timeout). A gate
that must stay shut, when it comes, belongs here and is not a hook — a hook
fails open.

**This is the one door.** Code mode calls `dispatch` once per tool a script uses,
so anything installed here covers scripts without knowing they exist. Two
dispatchers would let a gate be installed on one and not the other, with nothing
in the types or the tests to say which path was covered. The corollary: the
guardrail, living above this door, sees a script as one call however many it
makes inside.
"""

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
        # Built here, not by the caller: the dispatcher is the one place that
        # holds both the call and the reporter, so no caller can hand a tool
        # another call's id.
        context = ToolContext(call_id=call.id, progress=progress)
        return await tool.invoke(call.arguments, context=context)

    def _unknown(self, name: str) -> str:
        """Naming what *is* available turns a dead end into a correction the
        caller can act on next step, which is the whole reason an unknown tool is
        a Failure rather than an exception.
        """
        available = ", ".join(sorted(t.name for t in self._registry.all())) or "none"
        return f"tool {name!r} is not available. Available tools: {available}"
