"""Every tool there is, and the one way a call to any of them runs."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from harness.llm import ToolCall
from harness.tools.approval import ApprovalGate
from harness.tools.models.context import CallOrigin, ToolContext, ToolProgressReporter
from harness.tools.models.outcome import UNKNOWN_TOOL, Failure, Pending, ToolOutcome
from harness.tools.models.tool import Tool

logger = logging.getLogger("harness.tools")

Disposer = Callable[[], None]

ToolProvider = Callable[[], Iterable[Tool]]


class DuplicateToolError(RuntimeError):
    """Two tools registered under one name."""


class ToolService:
    """Static tools plus live providers, and the one dispatch every call goes through."""

    def __init__(
        self,
        tools: Iterable[Tool],
        *,
        gate: ApprovalGate,
        providers: Iterable[ToolProvider] = (),
    ) -> None:
        self._static: dict[str, Tool] = {}
        self._providers: list[ToolProvider] = list(providers)
        self._gate = gate
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> Disposer:
        """Add one tool. Returns a disposer that removes exactly it."""
        if tool.name in self._static:
            raise DuplicateToolError(f"{tool.name!r} is already registered")
        self._static[tool.name] = tool

        done = False

        def dispose() -> None:
            nonlocal done
            if done:
                return
            done = True
            self._static.pop(tool.name, None)

        return dispose

    def add_provider(self, provider: ToolProvider) -> Disposer:
        """Add a dynamic source, asked on every read."""
        self._providers.append(provider)

        done = False

        def dispose() -> None:
            nonlocal done
            if done:
                return
            done = True
            self._providers.remove(provider)

        return dispose

    def all(self) -> list[Tool]:
        """Every tool available right now."""
        resolved = dict(self._static)
        for provider in self._providers:
            try:
                offered = list(provider())
            except Exception:
                logger.warning("tool provider failed", exc_info=True)
                continue
            for tool in offered:
                if tool.name in resolved:
                    logger.warning("tool %r already provided; ignoring duplicate", tool.name)
                    continue
                resolved[tool.name] = tool
        return list(resolved.values())

    def get(self, name: str) -> Tool | None:
        """The tool called `name`, or `None`."""
        for tool in self.all():
            if tool.name == name:
                return tool
        return None

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
        tool = self.get(call.name)
        if tool is None:
            return Failure(UNKNOWN_TOOL, self._unknown_tool_message(call.name))
        context = ToolContext(call_id=call.id, progress=progress, origin=origin)
        return await tool.invoke(call.arguments, context=context)

    def _unknown_tool_message(self, name: str) -> str:
        """The failure text for a name nobody registered, naming what is available."""
        available = ", ".join(sorted(t.name for t in self.all())) or "none"
        return f"tool {name!r} is not available. Available tools: {available}"
