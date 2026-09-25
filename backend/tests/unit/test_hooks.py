"""The hook chain: typed decisions, fail-open, first non-None wins."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass

import pytest

from harness.agent.hooks import (
    CompletedCall,
    HookChain,
    Signature,
    StepDecision,
    StepHook,
    Tell,
    ToolHook,
    completed_calls,
)
from harness.agent.hooks import chain as chain_module
from harness.llm.messages import ToolCall, ToolMessage
from harness.session.models import ToolCallEvent, ToolResultEvent, TurnStart
from harness.tools.definition import BLOCKED, Ok, ToolOutcome
from tests.unit.helpers import new_session

CALL = ToolCall(id="c1", name="echo", arguments="{}")


@dataclass(frozen=True)
class Says(ToolHook):
    refusal: str | None = None
    note: str | None = None

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        return self.refusal

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        return self.note


class Raises(ToolHook):
    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        raise RuntimeError("bug in a hook")

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        raise RuntimeError("bug in a hook")


class RaisesAtStepEnd(StepHook):
    async def end_of_step(
        self, empties: int, prior: Sequence[CompletedCall]
    ) -> StepDecision | None:
        raise RuntimeError("bug in a step hook")


@dataclass(frozen=True)
class SaysAtStepEnd(StepHook):
    decision: StepDecision | None = None

    async def end_of_step(
        self, empties: int, prior: Sequence[CompletedCall]
    ) -> StepDecision | None:
        return self.decision


class Hangs(ToolHook):
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        self.started.set()
        await asyncio.Event().wait()
        return "never"

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        await asyncio.Event().wait()
        return "never"


class Sees(ToolHook):
    """Records what the contract handed it."""

    def __init__(self) -> None:
        self.seen: list[tuple[Signature, tuple[CompletedCall, ...]]] = []

    async def pre(self, sig: Signature, calls: Sequence[CompletedCall]) -> str | None:
        self.seen.append((sig, calls))
        return None

    async def post(
        self, sig: Signature, outcome: ToolOutcome, calls: Sequence[CompletedCall]
    ) -> str | None:
        self.seen.append((sig, calls))
        return None


async def test_an_empty_chain_decides_nothing() -> None:
    chain = HookChain()

    assert await chain.pre_tool_call(CALL, session=new_session()) is None
    assert await chain.post_tool_call(CALL, Ok(content="x"), session=new_session()) is None


async def test_first_non_none_wins_and_order_is_precedence() -> None:
    chain = HookChain(
        (Says(), Says(refusal="second", note="two"), Says(refusal="third", note="three"))
    )

    assert await chain.pre_tool_call(CALL, session=new_session()) == "second"
    assert await chain.post_tool_call(CALL, Ok(content="x"), session=new_session()) == "two"


async def test_a_raising_decision_hook_refuses_nothing_and_suppresses_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    chain = HookChain((Raises(), Says(refusal="ok", note="note")))

    with caplog.at_level(logging.ERROR, logger="harness.agent"):
        assert await chain.pre_tool_call(CALL, session=new_session()) == "ok"
        assert await chain.post_tool_call(CALL, Ok(content="x"), session=new_session()) == "note"

    assert "Raises.pre raised" in caplog.text
    assert "Raises.post raised" in caplog.text


async def test_a_hook_exceeding_the_timeout_is_skipped_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(chain_module, "HOOK_TIMEOUT_S", 0.01)
    chain = HookChain((Hangs(), Says(refusal="after")))

    with caplog.at_level(logging.WARNING, logger="harness.agent"):
        assert await chain.pre_tool_call(CALL, session=new_session()) == "after"

    assert "Hangs.pre exceeded" in caplog.text


async def test_cancellation_passes_through_a_hook() -> None:
    hanging = Hangs()
    chain = HookChain((hanging, Says(refusal="never")))
    task = asyncio.create_task(chain.pre_tool_call(CALL, session=new_session()))
    await hanging.started.wait()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_a_hook_is_handed_the_signature_and_the_settled_calls_not_the_session() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(
        ToolCallEvent(turn=0, step=0, call=ToolCall(id="a", name="echo", arguments="{}"))
    )
    session.append(
        ToolResultEvent(turn=0, step=0, message=ToolMessage(tool_call_id="a", content="hi"))
    )
    session.append(ToolCallEvent(turn=0, step=0, call=CALL))
    hook = Sees()

    await HookChain((hook,)).pre_tool_call(
        ToolCall(id="c1", name="echo", arguments='{ "x": 1 }'), session=session
    )

    sig, calls = hook.seen[0]
    assert sig == Signature(name="echo", args='{"x":1}')
    assert calls == (CompletedCall(name="echo", args="{}", error=None, text="hi"),)


async def test_the_fold_starts_over_each_turn_and_skips_the_hooks_own_refusals() -> None:
    session = new_session()
    session.append(TurnStart(turn=0))
    session.append(
        ToolCallEvent(turn=0, step=0, call=ToolCall(id="old", name="echo", arguments="{}"))
    )
    session.append(
        ToolResultEvent(turn=0, step=0, message=ToolMessage(tool_call_id="old", content="x"))
    )
    session.append(TurnStart(turn=1))
    session.append(
        ToolCallEvent(turn=1, step=0, call=ToolCall(id="b", name="echo", arguments="{}"))
    )
    session.append(
        ToolResultEvent(
            turn=1,
            step=0,
            message=ToolMessage(tool_call_id="b", content="error: not run"),
            error=BLOCKED,
        )
    )

    assert completed_calls(session) == ()


async def test_a_raising_step_hook_decides_nothing_and_the_next_one_is_asked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    chain = HookChain(step_hooks=(RaisesAtStepEnd(), SaysAtStepEnd(Tell("answer"))))

    with caplog.at_level(logging.ERROR, logger="harness.agent"):
        assert await chain.end_of_step(session=new_session()) == Tell("answer")

    assert "RaisesAtStepEnd.end_of_step raised" in caplog.text
    assert (
        await HookChain(step_hooks=(RaisesAtStepEnd(),)).end_of_step(session=new_session()) is None
    )
