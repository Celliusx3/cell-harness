"""The hook contract, and the chain that runs many hooks as one."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from harness.agent.hooks.calls import CompletedCall, Signature, completed_calls
from harness.llm.messages import ToolCall
from harness.session.log import Session
from harness.tools.definition import ToolOutcome

logger = logging.getLogger("harness.agent")

HOOK_TIMEOUT_S = 5.0


class ToolHook(ABC):
    """Something consulted before and after every tool call the model makes."""

    @abstractmethod
    async def pre(self, sig: Signature, prior: Sequence[CompletedCall]) -> str | None:
        """A reason to refuse the call, or `None` to run it."""

    @abstractmethod
    async def post(
        self, sig: Signature, outcome: ToolOutcome, prior: Sequence[CompletedCall]
    ) -> str | None:
        """Guidance for the model about this call, or `None` to say nothing."""


@dataclass(frozen=True)
class HookChain:
    """Many hooks as one."""

    hooks: tuple[ToolHook, ...] = ()

    async def pre_tool_call(self, call: ToolCall, *, session: Session) -> str | None:
        sig, calls = Signature.of(call), completed_calls(session)
        return await self._first(lambda hook: hook.pre(sig, calls), "pre")

    async def post_tool_call(
        self, call: ToolCall, outcome: ToolOutcome, *, session: Session
    ) -> str | None:
        sig, calls = Signature.of(call), completed_calls(session)
        return await self._first(lambda hook: hook.post(sig, outcome, calls), "post")

    async def _first(
        self, ask: Callable[[ToolHook], Awaitable[str | None]], point: str
    ) -> str | None:
        """The first hook with something to say, in registration order."""
        for hook in self.hooks:
            name = type(hook).__name__
            try:
                async with asyncio.timeout(HOOK_TIMEOUT_S):
                    decision = await ask(hook)
            except TimeoutError:
                logger.warning(
                    "hook %s.%s exceeded %.1fs and was skipped", name, point, HOOK_TIMEOUT_S
                )
                continue
            except Exception:
                logger.exception("hook %s.%s raised and was skipped", name, point)
                continue
            if decision is not None:
                return decision
        return None
