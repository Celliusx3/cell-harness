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

# How many selected tools a request carries at most — the most recently used.
# Selections would otherwise accumulate for the life of a conversation, and a
# long one that wandered across every server would end up carrying most of the
# catalog this pipeline exists to keep out of the request. At ~1K tokens a
# schema this bounds the addition at ~8K; a real task selects two to four. A
# tool that fell off is refused like one never selected, and the model selects
# it again.
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
        """What the model is offered this step — the only place visibility is decided.

        `default_tools` names what the model is given up front. Everything else
        stays registered and reachable — from a program, or by selecting it —
        but is not described in the request, which is what keeps that
        description from being re-uploaded with every message. An empty list
        means what it looks like: nothing offered, every direct call refused.

        `tools_selected` is what this conversation has selected by reading
        schemas (`Session.tools_selected()`), oldest first; only the last
        `MAX_TOOLS_SELECTED` are carried. Passed rather than read here because it
        is session state: this object outlives every conversation, and two of
        them have selected differently.
        """
        return [tool.spec() for tool in self._offered(tools_selected)]

    def _offered(self, tools_selected: Sequence[str]) -> list[ToolDefinition]:
        by_name = {t.name: t for t in self._registry.all()}
        # Skipping the absent rather than raising: a name here may belong to a
        # server that has not connected yet, or has gone away — or be the skill
        # tool on a day with no skills.
        offered = [by_name[n] for n in self._default if n in by_name]
        chosen = {tool.name for tool in offered}
        # Selected: the model read this tool's schema, so it may call it by
        # name. The most recent few only, then sorted so the request is the same
        # whatever order the log was read in — a prompt cache keys on bytes. A
        # name whose server has since gone is skipped, for the same reason as
        # above.
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
        """Run one of the model's own calls — if it was offered.

        **Registered is not offered; selected is.** The dispatcher resolves any
        registered name, because a script's calls need it to; that is the front
        door for everything. But a model that names a tool it was never shown
        has hallucinated it — observed with a 4B model that copied
        `instagram__fetch_reels` out of a skill body and called it as a tool,
        which ran, because nothing between the loop and the dispatcher asked
        whether it had been offered. So the offer is checked here, against the
        same `_offered` that built the request, and the refusal is a sequence
        rather than a wall: select the tool by reading its schema, then call it.
        That is the step a 4B model skipped when it guessed a return shape and
        got the answer wrong — here the harness insists on it. Scripts never
        pass through this method — the bridge is their route — so they are
        unaffected.

        Same computation as `specs()` on purpose, so what was shown and what is
        allowed cannot disagree.
        """
        if call.name not in {tool.name for tool in self._offered(tools_selected)}:
            return Failure(REFUSED, _not_offered(call.name))
        return await self._dispatcher.dispatch(call, progress=progress)


def _not_offered(name: str) -> str:
    # Prompt text is code. Deliberately does *not* list what exists — that list
    # is exactly what `list_functions` is for, and naming it here would let the
    # model skip reading the schema it is about to call against.
    return (
        f"{name!r} is not in your tool list. Select it by reading its schema with "
        "get_function_details — then it is, and you can call it directly. "
        "See list_functions for what exists."
    )
