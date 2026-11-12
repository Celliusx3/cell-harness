"""One turn's steps: ask the model, run what it asked for, repeat."""

from __future__ import annotations

import itertools
from collections.abc import AsyncIterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING

from harness.llm import (
    CONTEXT_WINDOW_EXCEEDED,
    IMAGES_OVER_LIMIT,
    ApplicationMessage,
    AssistantMessage,
    Completed,
    Failed,
    StreamEvent,
    TextChunk,
    ToolCallChunk,
)
from harness.prompts import APPROVAL_MODE_CHANGED
from harness.runtime.compaction import run_compaction, should_compact
from harness.runtime.events import (
    AgentCompleted,
    AgentFailed,
    AgentPending,
    ToolPending,
    TurnEvent,
)
from harness.runtime.hooks import GiveUp, Tell
from harness.runtime.inbox import claim_into
from harness.runtime.models import PICK_A_MODEL, NoModel
from harness.runtime.tool_run import run_tool_calls
from harness.session.compaction import CompactionEnd, CompactionPrune, CompactionTrigger
from harness.session.derive import through_hiding
from harness.session.images import ImagesHidden
from harness.session.log import Session
from harness.session.models import (
    ApplicationMessageEvent,
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
    StepStart,
    TurnEnd,
    TurnEndReason,
)

if TYPE_CHECKING:
    from harness.runtime.service import Runtime

NO_TERMINAL = "stream ended without a terminal event"


@dataclass(frozen=True)
class RetryStep:
    """The history was shrunk after a size refusal: run the same step again."""


@dataclass(frozen=True)
class TurnStep:
    """Where a step's appends land in the log: its turn, and its number within it."""

    turn: int
    step: int


async def run_turn(
    runtime: Runtime, session: Session, turn: int, *, bot_id: str
) -> AsyncIterator[TurnEvent]:
    """From an opened turn to its end: its events as they happen, then exactly one terminal."""
    step = 0
    outcome: AgentCompleted | AgentPending | AgentFailed

    try:
        for step in itertools.count():
            at = TurnStep(turn=turn, step=step)
            await _open_step(runtime, session, at, bot_id=bot_id)
            await _shrink_history_when_due(runtime, session, turn=turn, bot_id=bot_id)

            reply: Completed | Failed | RetryStep | None = None
            async with aclosing(_stream_reply(runtime, session, bot_id, at=at)) as chunks:
                async for event in chunks:
                    if isinstance(event, (TextChunk, ToolCallChunk)):
                        yield event
                    else:
                        reply = event
            assert reply is not None

            if isinstance(reply, (RetryStep, Failed)) or not reply.tool_calls:
                ended = await _outcome_without_tools(runtime, session, reply, at=at, bot_id=bot_id)
                if ended is None:
                    continue
                outcome = ended
                break

            pending: ToolPending | None = None
            async with aclosing(
                run_tool_calls(
                    runtime,
                    reply.tool_calls,
                    session=session,
                    turn=turn,
                    step=step,
                    bot_id=bot_id,
                )
            ) as results:
                async for event in results:
                    if isinstance(event, ToolPending):
                        pending = event
                    yield event
            if pending is not None:
                _close(session, turn, step, "pending")
                outcome = AgentPending(tool_call_id=pending.tool_call_id, name=pending.name)
                break
            session.append(StepEnd(turn=turn, step=step))
    except BaseException:
        _close(session, turn, step, "cancelled")
        raise
    yield outcome


async def _shrink_history_when_due(
    runtime: Runtime, session: Session, *, turn: int, bot_id: str
) -> None:
    """Compact before the step's request when the history has grown past `bot_id`'s line."""
    if should_compact(await runtime.models.model_for(bot_id), session):
        await _shrink_history(runtime, session, turn=turn, trigger="auto")


async def _outcome_without_tools(
    runtime: Runtime,
    session: Session,
    reply: Completed | Failed | RetryStep,
    *,
    at: TurnStep,
    bot_id: str,
) -> AgentCompleted | AgentFailed | None:
    """A step whose reply runs no tools: the turn's outcome, or `None` to run another step."""
    if isinstance(reply, RetryStep):
        return None
    if isinstance(reply, Failed):
        _close(session, at.turn, at.step, "failed")
        return AgentFailed(reason=reply.reason)
    decision = await runtime.hooks.end_of_step(session=session)
    if isinstance(decision, GiveUp):
        _close(session, at.turn, at.step, "failed")
        return AgentFailed(reason=decision.reason)
    if isinstance(decision, Tell):
        _tell(session, at.turn, at.step, decision.note)
        return None
    if await claim_into(runtime, session, turn=at.turn, bot_id=bot_id):
        session.append(StepEnd(turn=at.turn, step=at.step))
        return None
    _close(session, at.turn, at.step, "completed")
    return AgentCompleted(text=reply.full_text)


async def _stream_reply(
    runtime: Runtime, session: Session, bot_id: str, *, at: TurnStep
) -> AsyncIterator[TextChunk | ToolCallChunk | Completed | Failed | RetryStep]:
    """One request to `bot_id`'s model: its chunks, then `Completed`, `Failed` or `RetryStep`."""
    choice = await runtime.models.model_for(bot_id)
    if isinstance(choice, NoModel):
        refused = Failed(reason=PICK_A_MODEL)
        session.append(AssistantChunk(turn=at.turn, step=at.step, chunk=refused))
        yield refused
        return
    selected = session.tools_selected()
    specs = runtime.tools.specs(selected, sees_images=choice.vision) if runtime.tools else None
    context = await runtime.hooks.start_of_step()
    messages = runtime.request_messages(session, context, sees_images=choice.vision)
    if runtime.checkpoint is not None:
        await runtime.checkpoint(session)

    completed: Completed | None = None
    failed: Failed | None = None
    partial = ""
    try:
        async with aclosing(
            choice.client.stream_completion(messages, choice.model, tools=specs)
        ) as stream:
            async for event in stream:
                _log_chunk(session, event, at=at)
                if isinstance(event, TextChunk):
                    partial += event.text
                    yield event
                elif isinstance(event, ToolCallChunk):
                    yield event
                elif isinstance(event, Completed):
                    completed = event
                elif isinstance(event, Failed):
                    failed = event

        if failed is not None or completed is None:
            failure = failed if failed is not None else Failed(reason=NO_TERMINAL)
            yield await _failure_or_retry(runtime, session, failure, turn=at.turn)
            return

        session.append(
            AssistantMessageEvent(
                turn=at.turn,
                step=at.step,
                message=AssistantMessage(
                    content=completed.full_text, tool_calls=completed.tool_calls
                ),
                usage=completed.usage,
            )
        )
        yield completed
    except BaseException:
        _log_interrupted_reply(session, partial, turn=at.turn, step=at.step)
        raise


async def _failure_or_retry(
    runtime: Runtime, session: Session, failure: Failed, *, turn: int
) -> Failed | RetryStep:
    """`RetryStep` when the request was too big and the history shrank, else the failure."""
    if failure.code == CONTEXT_WINDOW_EXCEEDED and await _shrink_history(
        runtime, session, turn=turn, trigger="overflow"
    ):
        return RetryStep()
    if failure.code == IMAGES_OVER_LIMIT and _hide_images(session, failure, turn=turn):
        return RetryStep()
    return failure


def _log_chunk(session: Session, event: StreamEvent, *, at: TurnStep) -> None:
    """Log `event`, unless it is the adapter's own refusal of a request it never sent."""
    if isinstance(event, Failed) and event.images_to_hide is not None:
        return
    session.append(AssistantChunk(turn=at.turn, step=at.step, chunk=event))


def _hide_images(session: Session, failure: Failed, *, turn: int) -> bool:
    """Log a hide of as many more images as `failure` asks: `True` when one more could go."""
    if failure.images_to_hide is None:
        return False
    through = through_hiding(session.events(), failure.images_to_hide)
    if through is None:
        return False
    session.append(ImagesHidden(turn=turn, through=through))
    return True


def _log_interrupted_reply(session: Session, partial: str, *, turn: int, step: int) -> None:
    """Log the text the person already saw, when there is any, as an interrupted reply."""
    if partial:
        session.append(
            AssistantMessageEvent(
                turn=turn,
                step=step,
                message=AssistantMessage(content=partial),
                interrupted=True,
            )
        )


async def _shrink_history(
    runtime: Runtime, session: Session, *, turn: int, trigger: CompactionTrigger
) -> bool:
    """One compaction, run to its end: `True` when it pruned or wrote a summary."""
    shrank = False
    async with aclosing(run_compaction(runtime, session, turn=turn, trigger=trigger)) as events:
        async for event in events:
            if isinstance(event, CompactionPrune) or (
                isinstance(event, CompactionEnd) and event.succeeded
            ):
                shrank = True
    return shrank


async def _open_step(runtime: Runtime, session: Session, at: TurnStep, *, bot_id: str) -> None:
    """Open the step, then, past the first, read in what the person sent since the last."""
    _start_step_noting_mode_switch(runtime, session, at)
    if at.step > 0:
        await claim_into(runtime, session, turn=at.turn, bot_id=bot_id)


def _start_step_noting_mode_switch(runtime: Runtime, session: Session, at: TurnStep) -> None:
    """Open the step, and tell the model when the person switched the mode since the last one."""
    switch = runtime.approval_mode_switch(session)
    session.append(StepStart(turn=at.turn, step=at.step))
    if switch is not None:
        note = APPROVAL_MODE_CHANGED.format(before=switch.before, after=switch.after)
        message = ApplicationMessage(content=note)
        session.append(ApplicationMessageEvent(turn=at.turn, message=message))


def _tell(session: Session, turn: int, step: int, note: str) -> None:
    """Close the step with a note the model reads before the next request."""
    session.append(ApplicationMessageEvent(turn=turn, message=ApplicationMessage(content=note)))
    session.append(StepEnd(turn=turn, step=step))


def _close(session: Session, turn: int, step: int, reason: TurnEndReason) -> None:
    session.append(StepEnd(turn=turn, step=step))
    session.append(TurnEnd(turn=turn, reason=reason))
