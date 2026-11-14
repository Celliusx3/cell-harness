"""Opening one step of a turn: its start, a mode-switch note, and what the person sent since."""

from __future__ import annotations

from typing import TYPE_CHECKING

from harness.llm import ApplicationMessage
from harness.prompts import APPROVAL_MODE_CHANGED
from harness.runtime.inbox import log_waiting_messages
from harness.session.domain.log import Session
from harness.session.domain.models import ApplicationMessageEvent, StepStart

if TYPE_CHECKING:
    from harness.runtime.service import Runtime


async def open_step(
    runtime: Runtime, session: Session, *, turn: int, step: int, bot_id: str
) -> None:
    """Open the step, then, past the first, read in what the person sent since the last."""
    _start_step_noting_mode_switch(runtime, session, turn=turn, step=step)
    if step > 0:
        await log_waiting_messages(runtime, session, turn=turn, bot_id=bot_id)


def _start_step_noting_mode_switch(
    runtime: Runtime, session: Session, *, turn: int, step: int
) -> None:
    """Open the step, and tell the model when the person switched the mode since the last one."""
    switch = runtime.approval_mode_switch(session)
    session.append(StepStart(turn=turn, step=step))
    if switch is not None:
        note = APPROVAL_MODE_CHANGED.format(before=switch.before, after=switch.after)
        message = ApplicationMessage(content=note)
        session.append(ApplicationMessageEvent(turn=turn, message=message))
