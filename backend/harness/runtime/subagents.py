"""Subagents: one task each, run to its end by a copy of a runtime, in a session log of its own."""

from __future__ import annotations

import dataclasses
from contextlib import aclosing
from dataclasses import dataclass

from harness.prompts import SUBAGENT_INTRO
from harness.runtime.events import AgentCompleted, AgentFailed, AgentPending, TurnEvent
from harness.runtime.service import Runtime
from harness.session.service import SessionService
from harness.tools.native.subagent import (
    SubagentAnswered,
    SubagentOutcome,
    SubagentStopped,
    SubagentTask,
)


@dataclass(frozen=True)
class Subagents:
    """Runs each subagent as `runtime`, logging its steps in `sessions` under the subagent's id."""

    runtime: Runtime
    sessions: SessionService

    async def __call__(
        self, subagent_id: str, task: SubagentTask, *, bot_id: str
    ) -> SubagentOutcome:
        """Run `task` for `bot_id` in a new session `subagent_id`, and report how its turn ended."""
        session = await self.sessions.create(subagent_id)
        subagent = dataclasses.replace(
            self.runtime,
            guidance=SUBAGENT_INTRO.format(name=task.name) + self.runtime.guidance,
            checkpoint=self.sessions.flush,
        )
        last: TurnEvent | None = None
        try:
            async with aclosing(subagent.run(task.task, session=session, bot_id=bot_id)) as events:
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
