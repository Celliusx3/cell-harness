"""`run_subagent`: one to four tasks, each run by its own subagent at the same time."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Protocol

from harness.tools.models.context import ToolContext
from harness.tools.models.outcome import Ok, ToolOutcome
from harness.tools.models.tool import Tool
from harness.tools.native.subagent.models import (
    SubagentArgs,
    SubagentOutcome,
    SubagentReply,
    SubagentTask,
)

RUN_SUBAGENT = "run_subagent"

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


class SubagentRunner(Protocol):
    """Runs one task as the subagent `subagent_id` for the bot `bot_id`, to its end."""

    async def __call__(
        self, subagent_id: str, task: SubagentTask, *, bot_id: str
    ) -> SubagentOutcome: ...


def run_subagent_tool(runner: SubagentRunner) -> Tool[SubagentArgs]:
    """The tool that runs every task at once, each by its own subagent, and gathers their ends."""

    async def execute(args: SubagentArgs, context: ToolContext) -> ToolOutcome:
        try:
            async with asyncio.TaskGroup() as group:
                running = [
                    group.create_task(
                        runner(f"{context.call_id}.{index}", task, bot_id=context.origin.bot_id)
                    )
                    for index, task in enumerate(args.tasks)
                ]
        except ExceptionGroup as broken:
            raise broken.exceptions[0] from broken
        return Ok(_answers_text(args.tasks, [subagent.result() for subagent in running]))

    return Tool.from_model(
        name=RUN_SUBAGENT, description=_DESCRIPTION, args_model=SubagentArgs, execute=execute
    )


def _answers_text(tasks: Sequence[SubagentTask], outcomes: Sequence[SubagentOutcome]) -> str:
    """One section per subagent, in task order, headed by its name."""
    return "\n\n".join(
        _section(task, outcome) for task, outcome in zip(tasks, outcomes, strict=True)
    )


def _section(task: SubagentTask, outcome: SubagentOutcome) -> str:
    if isinstance(outcome, SubagentReply):
        return f"## {task.name}\n{outcome.text}"
    return f"## {task.name}\nstopped: {outcome.reason}"
