"""The set of tools an agent can call."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from harness.tools.definition import ToolDefinition

logger = logging.getLogger("harness.tools")

Disposer = Callable[[], None]

ToolProvider = Callable[[], Iterable[ToolDefinition]]


class DuplicateToolError(RuntimeError):
    """Two tools registered under one name."""


class ToolRegistry:
    """Static tools plus live providers."""

    def __init__(
        self,
        tools: Iterable[ToolDefinition] = (),
        providers: Iterable[ToolProvider] = (),
    ) -> None:
        self._static: dict[str, ToolDefinition] = {}
        self._providers: list[ToolProvider] = list(providers)
        for tool in tools:
            self.register(tool)

    def register(self, tool: ToolDefinition) -> Disposer:
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

    def all(self) -> list[ToolDefinition]:
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

    def get(self, name: str) -> ToolDefinition | None:
        """The tool called `name`, or `None`."""
        for tool in self.all():
            if tool.name == name:
                return tool
        return None
