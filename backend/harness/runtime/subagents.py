"""Subagents: one task each, run to its end by a copy of a runtime, in a session log of its own."""

from __future__ import annotations

from dataclasses import dataclass

from harness.prompts import SUBAGENT_INTRO
from harness.runtime.events import AgentCompleted, AgentFailed, AgentPending, TurnEvent
from harness.runtime.run_to_end import HelperTurn, run_to_end
from harness.runtime.service import Runtime
from harness.session.domain.models import ApprovalModeChanged
from harness.session.service.session_service import SessionService
from harness.tools.domain.decision import ApprovalMode
from harness.tools.native.subagent import (
    SubagentOutcome,
    SubagentReply,
    SubagentStop,
    SubagentTask,
)


@dataclass(frozen=True)
class Subagents:
    """Runs each subagent as `runtime`, logging its steps in `sessions` under the subagent's id."""

    runtime: Runtime
    sessions: SessionService

    async def __call__(
        self, subagent_id: str, task: SubagentTask, *, bot_id: str, mode: ApprovalMode
    ) -> SubagentOutcome:
        """Run `task` for `bot_id` in `mode` in a new session `subagent_id`, and report its end."""
        session = await self.sessions.create(subagent_id)
        session.append(ApprovalModeChanged(mode=mode))
        turn = HelperTurn(
            intro=SUBAGENT_INTRO.format(name=task.name), prompt=task.task, bot_id=bot_id
        )
        last = await run_to_end(self.runtime, self.sessions, session, turn)
        return _subagent_outcome(last)


def _subagent_outcome(ending: TurnEvent | None) -> SubagentOutcome:
    """How a subagent's turn ended, from the last event its run yielded."""
    match ending:
        case AgentCompleted(text=text):
            return SubagentReply(text=text)
        case AgentPending(name=name):
            return SubagentStop(
                reason=f"it called {name}, which needs the user, and a helper cannot reach "
                f"the user. Call {name} yourself if it is still needed."
            )
        case AgentFailed(reason=reason):
            return SubagentStop(reason=f"its turn failed: {reason}")
        case _:
            raise ValueError(f"a helper's run ended without a terminal event: {ending!r}")
