"""The set of tools an agent can call.

Two sources, and the second is the point: **static** tools registered directly,
plus **providers** — callables asked afresh on every read. A provider is how a
dynamic source contributes without anyone rebuilding the agent, which is what
lets an MCP server connected mid-conversation (phase 5) be callable on the very
next turn.

That is also why `specs()` and `get()` re-resolve rather than caching. Caching
would be faster and would freeze each agent's tool set at the moment it was
composed — the exact bug the provider seam exists to avoid.

A flat dict for now. Per-agent *layers* arrive in phase 13, when a plugin first
registers into one agent's world; per-agent *selection* (phase 9) needs no layers
at all — it wraps a provider and filters what it yields.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from harness.tools.definition import ToolDefinition

logger = logging.getLogger("harness.tools")

Disposer = Callable[[], None]

# Yields whatever tools its source currently offers. Asked on every read, so
# connect and disconnect take effect without a registration step.
ToolProvider = Callable[[], Iterable[ToolDefinition]]


class DuplicateToolError(RuntimeError):
    """Two tools registered under one name.

    Fails loudly rather than letting the later win: which one the model reaches
    would depend on registration order, and a silently shadowed tool is a bug
    that only shows up as the model getting an answer from the wrong place.
    """


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
        """Every tool available right now.

        A provider that raises is logged and contributes nothing. One broken
        source must not take the whole tool set down with it — the model losing
        every tool is far worse than losing one server's.

        Static tools win a name collision with a provider's, and the first
        provider to offer a name wins over later ones. Deterministic rather than
        an error, because a remote source's tool names are not ours to control
        and a collision must not break the turn.
        """
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
        """The tool called `name`, or `None`.

        Resolved live: a tool contributed this turn is dispatchable this turn.
        """
        for tool in self.all():
            if tool.name == name:
                return tool
        return None
