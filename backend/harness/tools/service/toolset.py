"""What the model is offered — and, for its own calls, what it may run."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from harness.llm import ToolCall, ToolSpec
from harness.tools.domain.context import CallOrigin, ToolProgressReporter
from harness.tools.domain.decision import ApprovalMode
from harness.tools.domain.outcome import REFUSED, Failure, ToolOutcome
from harness.tools.domain.tool import Tool
from harness.tools.service.tool_service import ToolService

MAX_TOOLS_SELECTED = 8


class ToolChoices(Protocol):
    """A conversation's choices about tools: what the model selected, what the person allowed."""

    def tools_selected(self) -> tuple[str, ...]: ...

    def speaker_granted_tools(self) -> frozenset[str]: ...

    def approval_mode(self, default: ApprovalMode) -> ApprovalMode: ...


class Toolset:
    """The tool list one step is built from."""

    def __init__(
        self,
        tool_service: ToolService,
        default_tools: Sequence[str],
        *,
        sight_tools: frozenset[str],
    ) -> None:
        self.tool_service = tool_service
        self._default_tools = tuple(default_tools)
        self._sight_tools = sight_tools

    @property
    def default_mode(self) -> ApprovalMode:
        """The mode a chat follows until the person switches it."""
        return self.tool_service.approvals.default_mode

    def approval_mode(self, session: ToolChoices) -> ApprovalMode:
        """The mode `session`'s calls run under: its latest switch, else the configured default."""
        return session.approval_mode(self.default_mode)

    def specs(self, tools_selected: Sequence[str] = (), *, sees_images: bool) -> list[ToolSpec]:
        """What the model is offered this step — the only place visibility is decided."""
        return [tool.spec() for tool in self._offered_tools(tools_selected, sees_images)]

    def _offered_tools(self, tools_selected: Sequence[str], sees_images: bool) -> list[Tool]:
        """The defaults, then the latest selections; `sight_tools` only to a model that sees."""
        by_name = {
            t.name: t
            for t in self.tool_service.all()
            if sees_images or t.name not in self._sight_tools
        }
        defaults = [by_name[n] for n in self._default_tools if n in by_name]
        default_names = {tool.name for tool in defaults}
        recent = tuple(tools_selected)[-MAX_TOOLS_SELECTED:]
        selected = sorted(
            (by_name[n] for n in recent if n in by_name and n not in default_names),
            key=lambda tool: tool.name,
        )
        return [*defaults, *selected]

    async def execute(
        self,
        call: ToolCall,
        *,
        progress: ToolProgressReporter,
        origin: CallOrigin,
        session: ToolChoices,
        sees_images: bool,
    ) -> ToolOutcome:
        """Run one of the model's own calls if it was offered, unasked if allowed for the chat."""
        offered = self._offered_tools(session.tools_selected(), sees_images)
        if call.name not in {tool.name for tool in offered}:
            return Failure(REFUSED, _not_offered_message(call.name))
        return await self.tool_service.dispatch(
            call,
            progress=progress,
            approved=call.name in session.speaker_granted_tools(),
            origin=origin,
        )

    async def execute_approved(
        self, call: ToolCall, *, progress: ToolProgressReporter, origin: CallOrigin
    ) -> ToolOutcome:
        """Run the call the person approved on its card; their yes skips the offered check."""
        return await self.tool_service.dispatch(
            call, progress=progress, approved=True, origin=origin
        )


def _not_offered_message(name: str) -> str:
    return (
        f"{name!r} is not in your tool list. Select it by reading its schema with "
        "get_function_details — then it is, and you can call it directly. "
        "See list_functions for what exists."
    )
