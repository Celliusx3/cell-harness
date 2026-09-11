"""What the model is offered — and, for its own calls, what it may run.

Deciding the tool list and running a tool are two jobs that change for different
reasons, so they are two objects. `ToolDispatcher` runs things; this decides what
the model is told about, and holds the model to it: a call the model makes by
name is refused unless that name was in the offer. See `execute`.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness.llm.messages import ToolCall, ToolSpec
from harness.tools.definition import REFUSED, Failure, ToolDefinition, ToolOutcome
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
        stays registered and callable from a program — it is simply not described
        in the request, which is what keeps that description from being
        re-uploaded with every message. Empty offers everything, which is the
        composition most tests build; it is passed rather than defaulted, because
        "offer everything" is a decision and not an absence.

        Today the harness passes code mode's three plus the skill tool, so the
        model reaches its capabilities by writing a program. Adding a name here is
        how a tool earns a place in every request instead — a clock, or an MCP
        tool used so often that a discovery step for it is waste.
        """
        return [tool.spec() for tool in self._offered()]

    def _offered(self) -> list[ToolDefinition]:
        by_name = {t.name: t for t in self._registry.all()}
        if not self._default:
            return list(by_name.values())
        # Skipping the absent rather than raising: a name here may belong to a
        # server that has not connected yet, or has gone away — or be the skill
        # tool on a day with no skills.
        return [by_name[n] for n in self._default if n in by_name]

    async def execute(self, call: ToolCall, *, progress: ToolProgressReporter) -> ToolOutcome:
        """Run one of the model's own calls — if it was offered.

        **Registered is not offered.** The dispatcher resolves any registered
        name, because a script's calls need it to; that is the front door for
        everything. But a model that names a tool it was never shown has
        hallucinated it — observed with a 4B model that copied
        `instagram__fetch_reels` out of a skill body and called it as a tool,
        which ran, because nothing between the loop and the dispatcher asked
        whether it had been offered. It worked; it was also an unmetered second
        route around code mode, and the request stopped being the record of what
        the model could call directly. So the offer is checked here, against the
        same `_offered` that built the request, and the refusal names the route
        that does exist. Scripts never pass through this method — the bridge is
        their route — so they are unaffected.

        Same computation as `specs()` on purpose, so what was shown and what is
        allowed cannot disagree.
        """
        if call.name not in {tool.name for tool in self._offered()}:
            return Failure(REFUSED, _not_offered(call.name))
        return await self._dispatcher.dispatch(call, progress=progress)


def _not_offered(name: str) -> str:
    # Prompt text is code. Deliberately does *not* list what exists — that list
    # is exactly what `list_functions` is for, and naming it here would advertise
    # the direct route this refusal closes.
    return (
        f"{name!r} is not in your tool list and cannot be called directly. "
        "Capabilities are called from a program: see list_functions."
    )
