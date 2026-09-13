"""The hook contract, and the chain that runs many hooks as one.

Two points, and their return types say what they may do:

- `pre -> str | None` — a reason to **refuse**, or `None` to let the call run.
  Refusal is pre-execution: the tool never starts.
- `post -> str | None` — guidance for the model, or `None`. The loop logs it
  as a `user/message` from the application once the step's calls settle, so it
  reaches the model beside the tool results, never inside one.

A hook does not see the session. The chain folds it once per call (`calls.py`)
and hands every hook the call's signature and the turn so far — every hook
written so far wanted exactly that and nothing else.

Because the decisions are typed returns rather than free-form payloads, a hook
physically cannot hand back a malformed directive, and there is nothing to
validate. cell-bot has five points; the three observers (`on_run_start`,
`on_run_end`, `post_tool_call`-as-observer) have no consumer here and are not
built. cell-bot's `transform_tool_result` *replaces*; ours only speaks, because
the one consumer — the guardrail — comments on a result and never rewrites it.

**A decision hook fails open.** `HookChain` awaits each hook under a timeout;
one that raises or runs long is logged and contributes nothing, and the next
hook is asked. So "registered" must never be read as "enforcing": a door that
must stay shut is not a hook — the pipeline's refusal of an unoffered name is
the example. First non-`None` wins, so **ordering is precedence**.

The timeout is the improvement on cell-bot, whose hooks run inline with none: a
slow hook there stalls every conversation's stream.
"""

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

# Per hook, per call. Generous for a fold over one turn's log; short enough that
# a hook doing I/O it should not is noticed as a delay, not a hang.
HOOK_TIMEOUT_S = 5.0


class ToolHook(ABC):
    """Something consulted before and after every tool call the model makes."""

    @abstractmethod
    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        """A reason to refuse the call, or `None` to run it."""

    @abstractmethod
    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        """Guidance for the model about this call, or `None` to say nothing."""


@dataclass(frozen=True)
class HookChain:
    """Many hooks as one. Empty by default, so the loop runs unhooked.

    The loop hands it the call and the session; it folds them once and asks
    each hook over the result.
    """

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
            except Exception:  # noqa: BLE001 — a hook's bug must not decide anything
                logger.exception("hook %s.%s raised and was skipped", name, point)
                continue
            if decision is not None:
                return decision
        return None
