"""The hook contract, and the chain that runs many hooks as one."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from harness.agent.hooks.calls import CompletedCall, Signature, completed_calls, empty_replies
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
class Tell:
    """What the model is told, as its own message, before the next step."""

    note: str


@dataclass(frozen=True)
class GiveUp:
    """Why the turn ends failed."""

    reason: str


StepDecision = Tell | GiveUp


class StepHook(ABC):
    """Something consulted when a step ends without a tool call: the model has answered."""

    @abstractmethod
    async def end_of_step(
        self, empties: int, prior: Sequence[CompletedCall]
    ) -> StepDecision | None:
        """What to do after the turn's `empties`-th blank reply, or `None` to accept the answer."""


H = TypeVar("H", ToolHook, StepHook)
D = TypeVar("D")


@dataclass(frozen=True)
class HookChain:
    """Many hooks as one."""

    hooks: tuple[ToolHook, ...] = ()
    steps: tuple[StepHook, ...] = ()

    async def pre_tool_call(self, call: ToolCall, *, session: Session) -> str | None:
        sig, calls = Signature.of(call), completed_calls(session)
        return await self._first(self.hooks, lambda hook: hook.pre(sig, calls), "pre")

    async def post_tool_call(
        self, call: ToolCall, outcome: ToolOutcome, *, session: Session
    ) -> str | None:
        sig, calls = Signature.of(call), completed_calls(session)
        return await self._first(self.hooks, lambda hook: hook.post(sig, outcome, calls), "post")

    async def end_of_step(self, *, session: Session) -> StepDecision | None:
        empties, calls = empty_replies(session), completed_calls(session)
        return await self._first(
            self.steps, lambda hook: hook.end_of_step(empties, calls), "end_of_step"
        )

    async def _first(
        self, hooks: Sequence[H], ask: Callable[[H], Awaitable[D | None]], point: str
    ) -> D | None:
        """The first hook with something to say, in registration order."""
        for hook in hooks:
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
