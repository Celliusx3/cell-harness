"""`run_subagent` over a stand-in runner: what it hands each subagent, and what it hands back."""

from __future__ import annotations

import asyncio
import json

import pytest

from harness.tools.definition import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.subagent import (
    RUN_SUBAGENT,
    SubagentAnswered,
    SubagentOutcome,
    SubagentStopped,
    SubagentTask,
    run_subagent_tool,
)
from tests.unit.helpers import context_for


class Recording:
    """A runner that answers from a table and remembers what it was asked."""

    def __init__(self, outcomes: dict[str, SubagentOutcome]) -> None:
        self._outcomes = outcomes
        self.asked: list[tuple[str, SubagentTask]] = []

    async def __call__(self, subagent_id: str, task: SubagentTask) -> SubagentOutcome:
        self.asked.append((subagent_id, task))
        return self._outcomes[task.name]


def _tasks(*names: str) -> str:
    return json.dumps({"tasks": [{"name": n, "task": f"look up {n}"} for n in names]})


async def test_each_task_goes_to_its_own_subagent_and_every_answer_comes_back() -> None:
    runner = Recording(
        {
            "aapl": SubagentAnswered(text="AAPL grew 2%."),
            "msft": SubagentStopped(reason="its turn failed: timeout"),
        }
    )
    tool = run_subagent_tool(runner)

    outcome = await tool.invoke(_tasks("aapl", "msft"), context=context_for("call-9"))

    assert [subagent_id for subagent_id, _ in runner.asked] == ["call-9.0", "call-9.1"]
    assert [task.task for _, task in runner.asked] == ["look up aapl", "look up msft"]
    assert isinstance(outcome, Ok)
    assert outcome.text == "## aapl\nAAPL grew 2%.\n\n## msft\nstopped: its turn failed: timeout"


async def test_more_than_four_tasks_are_refused_not_cut() -> None:
    runner = Recording({})
    tool = run_subagent_tool(runner)

    outcome = await tool.invoke(_tasks("a", "b", "c", "d", "e"), context=context_for())

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert runner.asked == []


async def test_no_tasks_are_refused() -> None:
    outcome = await run_subagent_tool(Recording({})).invoke(_tasks(), context=context_for())

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS


async def test_subagents_run_at_the_same_time() -> None:
    started = 0
    both = asyncio.Event()

    async def runner(subagent_id: str, task: SubagentTask) -> SubagentOutcome:
        nonlocal started
        started += 1
        if started == 2:
            both.set()
        await both.wait()
        return SubagentAnswered(text=task.name)

    async with asyncio.timeout(2):
        outcome = await run_subagent_tool(runner).invoke(_tasks("a", "b"), context=context_for())

    assert isinstance(outcome, Ok)


async def test_stopping_the_call_stops_every_subagent() -> None:
    cancelled: list[str] = []
    running = 0

    async def runner(subagent_id: str, task: SubagentTask) -> SubagentOutcome:
        nonlocal running
        running += 1
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(subagent_id)
            raise
        return SubagentAnswered(text="never")

    call = asyncio.create_task(
        run_subagent_tool(runner).invoke(_tasks("a", "b"), context=context_for("c"))
    )
    async with asyncio.timeout(2):
        while running < 2:
            await asyncio.sleep(0)
    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call

    assert sorted(cancelled) == ["c.0", "c.1"]


async def test_a_subagent_that_breaks_stops_the_others_and_says_why() -> None:
    cancelled: list[str] = []

    async def runner(subagent_id: str, task: SubagentTask) -> SubagentOutcome:
        if task.name == "a":
            await asyncio.sleep(0)
            raise RuntimeError("disk full")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(subagent_id)
            raise
        return SubagentAnswered(text="never")

    async with asyncio.timeout(2):
        outcome = await run_subagent_tool(runner).invoke(_tasks("a", "b"), context=context_for("c"))

    assert isinstance(outcome, Failure)
    assert "disk full" in outcome.message
    assert cancelled == ["c.1"]


async def test_the_example_in_the_description_runs() -> None:
    tool = run_subagent_tool(Recording({}))
    example = tool.description.split(f"{RUN_SUBAGENT}(", 1)[1].rsplit(")", 1)[0]
    names = [task["name"] for task in json.loads(example)["tasks"]]
    runner = Recording({name: SubagentAnswered(text=f"{name} done") for name in names})

    outcome = await run_subagent_tool(runner).invoke(example, context=context_for())

    assert isinstance(outcome, Ok)
    assert len(names) >= 2
    for name in names:
        assert f"## {name}\n{name} done" in outcome.text
