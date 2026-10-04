"""`run_subagent`: one to four tasks, each run by its own subagent at the same time."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from harness.tools.context import ToolContext
from harness.tools.definition import Ok, ToolDefinition, ToolOutcome

RUN_SUBAGENT = "run_subagent"
MAX_SUBAGENTS = 4

_DESCRIPTION = (
    "Hand one to four independent tasks to helpers that work at the same time, and get one "
    "short answer back from each. A helper sees none of this conversation, so write each task "
    "to stand alone: what to find, which tools to use, and what to return. Helpers have your "
    "tools except this one, cannot ask the user anything, and are gone once they answer. Use "
    "it when a request splits into parts that each need several tool calls, for example: "
    'run_subagent({"tasks": [{"name": "aapl", "task": "Get Apple\'s (AAPL) revenue for its '
    "last four fiscal years with the markets functions and return the year-on-year "
    'growth."}, {"name": "msft", "task": "Get Microsoft\'s (MSFT) revenue for its last four '
    'fiscal years with the markets functions and return the year-on-year growth."}]})'
)


class SubagentTask(BaseModel):
    """One helper's job: a label for its answer, and the task it is given."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        description="A short label for this helper, shown with its answer, e.g. 'aapl'."
    )
    task: str = Field(
        description="The whole task, written to stand alone: the helper sees none of this "
        "conversation."
    )


class SubagentArgs(BaseModel):
    """What the model passes to `run_subagent`."""

    tasks: list[SubagentTask] = Field(
        min_length=1,
        max_length=MAX_SUBAGENTS,
        description="One to four tasks; their helpers run at the same time.",
    )


@dataclass(frozen=True)
class SubagentAnswered:
    """The subagent's turn completed with this reply."""

    text: str


@dataclass(frozen=True)
class SubagentStopped:
    """The subagent's turn ended without a reply, for this reason."""

    reason: str


SubagentOutcome = SubagentAnswered | SubagentStopped


class SubagentRunner(Protocol):
    """Runs one task as the subagent `subagent_id`, to its end."""

    async def __call__(self, subagent_id: str, task: SubagentTask) -> SubagentOutcome: ...


def run_subagent_tool(runner: SubagentRunner) -> ToolDefinition[SubagentArgs]:
    """The tool that runs every task at once, each by its own subagent, and gathers their ends."""

    async def execute(args: SubagentArgs, context: ToolContext) -> ToolOutcome:
        try:
            async with asyncio.TaskGroup() as group:
                running = [
                    group.create_task(runner(f"{context.call_id}.{index}", task))
                    for index, task in enumerate(args.tasks)
                ]
        except ExceptionGroup as broken:
            raise broken.exceptions[0] from broken
        return Ok(_answers_text(args.tasks, [subagent.result() for subagent in running]))

    return ToolDefinition.from_model(
        name=RUN_SUBAGENT, description=_DESCRIPTION, args_model=SubagentArgs, execute=execute
    )


def _answers_text(tasks: Sequence[SubagentTask], outcomes: Sequence[SubagentOutcome]) -> str:
    """One section per subagent, in task order, headed by its name."""
    return "\n\n".join(
        _section(task, outcome) for task, outcome in zip(tasks, outcomes, strict=True)
    )


def _section(task: SubagentTask, outcome: SubagentOutcome) -> str:
    if isinstance(outcome, SubagentAnswered):
        return f"## {task.name}\n{outcome.text}"
    return f"## {task.name}\nstopped: {outcome.reason}"
