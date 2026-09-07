"""What the model is offered, and nothing else.

Deciding the tool list and running a tool are two jobs that change for different
reasons, so they are two objects. `ToolDispatcher` runs things; this decides what
the model is told about. `execute` stays here as a delegation so the loop keeps
one collaborator — see its docstring.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import ToolCall, ToolSpec
from harness.tools.definition import ToolOutcome
from harness.tools.dispatcher import ToolDispatcher
from harness.tools.progress import ToolProgressReporter
from harness.tools.registry import ToolRegistry


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

    def specs(self) -> list[ToolSpec]:
        """What the model is offered this step — the only place visibility is decided.

        `default_tools` names what the model is given up front. Everything else
        stays registered and callable — it is simply not described in the
        request, which is what keeps that description from being re-uploaded
        with every message. Empty offers everything, which is the composition
        most tests build; it is passed rather than defaulted, because "offer
        everything" is a decision and not an absence.

        Today the harness passes code mode's three, so the model reaches its
        capabilities by writing a program. Adding a name here is how a tool
        earns a place in every request instead — a clock, or an MCP tool used so
        often that a discovery step for it is waste.
        """
        by_name = {t.name: t for t in self._registry.all()}
        if not self._default:
            return [tool.spec() for tool in by_name.values()]
        # Skipping the absent rather than raising: a name here may belong to a
        # server that has not connected yet, or has gone away.
        return [by_name[n].spec() for n in self._default if n in by_name]

    async def execute(self, call: ToolCall, *, progress: ToolProgressReporter) -> ToolOutcome:
        """Run one call, by handing it to the dispatcher.

        A pass-through on purpose: it keeps `LoopAgent` depending on one
        collaborator rather than two. Moving it onto the loop is a later change
        that does not undo this split.
        """
        return await self._dispatcher.dispatch(call, progress=progress)
