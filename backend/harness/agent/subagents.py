"""Subagents: one task each, run to its end by a copy of an agent, in a session log of its own."""

from __future__ import annotations

import dataclasses
from contextlib import aclosing
from dataclasses import dataclass

from harness.agent.events import AgentCompleted, AgentFailed, AgentPending, TurnEvent
from harness.agent.loop import LoopAgent
from harness.session.service import SessionService
from harness.tools.native.subagent import (
    SubagentAnswered,
    SubagentOutcome,
    SubagentStopped,
    SubagentTask,
)


def _subagent_intro(name: str) -> str:
    """What a subagent is told ahead of the agent's own prompt."""
    return (
        f"You are a helper named {name}, started by the main assistant to do one task as part "
        "of its answer to the user. Nobody will read your questions, so do not ask any: do the "
        "task with your tools, then reply with a short result. That reply is all the main "
        "assistant receives."
    )


@dataclass(frozen=True)
class Subagents:
    """Runs each subagent as `agent`, logging its steps in `sessions` under the subagent's id."""

    agent: LoopAgent
    sessions: SessionService

    async def __call__(self, subagent_id: str, task: SubagentTask) -> SubagentOutcome:
        """Run `task` in a new session `subagent_id`, and report how its turn ended."""
        session = await self.sessions.create(subagent_id)
        subagent = dataclasses.replace(
            self.agent,
            system_prompt=_subagent_intro(task.name) + self.agent.system_prompt,
            checkpoint=self.sessions.flush,
        )
        last: TurnEvent | None = None
        try:
            async with aclosing(subagent.run(task.task, session=session)) as events:
                async for event in events:
                    last = event
        finally:
            await self.sessions.flush(session)
        return _subagent_outcome(last)


def _subagent_outcome(ending: TurnEvent | None) -> SubagentOutcome:
    """How a subagent's turn ended, from the last event its run yielded."""
    match ending:
        case AgentCompleted(text=text):
            return SubagentAnswered(text=text)
        case AgentPending(name=name):
            return SubagentStopped(
                reason=f"it called {name}, which needs the user, and a helper cannot reach "
                f"the user. Call {name} yourself if it is still needed."
            )
        case AgentFailed(reason=reason):
            return SubagentStopped(reason=f"its turn failed: {reason}")
        case _:
            raise ValueError(f"a helper's run ended without a terminal event: {ending!r}")
