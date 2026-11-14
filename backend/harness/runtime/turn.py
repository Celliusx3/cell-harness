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
    Completion,
    StreamEvent,
    StreamFailure,
    TextChunk,
    ToolCallChunk,
)
from harness.runtime.compaction import run_compaction, should_compact
from harness.runtime.events import (
    AgentCompleted,
    AgentFailed,
    AgentPending,
    TurnEvent,
)
from harness.runtime.hooks import GiveUp, Tell
from harness.runtime.inbox import log_waiting_messages
from harness.runtime.models import PICK_A_MODEL, NoModel
from harness.runtime.step_open import open_step
from harness.runtime.step_tools import NextStep, StepEnding, close_turn, run_step_tools
from harness.session.domain.compaction import CompactionEnd, CompactionPrune, CompactionTrigger
from harness.session.domain.images import ImagesHidden
from harness.session.domain.log import Session
from harness.session.domain.model_history import hide_through_for_fewer_images
from harness.session.domain.models import (
    ApplicationMessageEvent,
    AssistantChunk,
    AssistantMessageEvent,
    StepEnd,
)

if TYPE_CHECKING:
    from harness.runtime.service import Runtime

NO_TERMINAL_REASON = "stream ended without a terminal event"


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
            await open_step(runtime, session, turn=turn, step=step, bot_id=bot_id)
            await _shrink_history_when_due(runtime, session, turn=turn, bot_id=bot_id)

            reply: Completion | StreamFailure | RetryStep | None = None
            async with aclosing(_stream_reply(runtime, session, bot_id, at=at)) as chunks:
                async for event in chunks:
                    if isinstance(event, (TextChunk, ToolCallChunk)):
                        yield event
                    else:
                        reply = event
            assert reply is not None

            if isinstance(reply, (RetryStep, StreamFailure)) or not reply.tool_calls:
                ended = await _outcome_without_tools(runtime, session, reply, at=at, bot_id=bot_id)
                if ended is None:
                    continue
                outcome = ended
                break

            ending: StepEnding | None = None
            async with aclosing(
                run_step_tools(
                    runtime, session, reply.tool_calls, turn=turn, step=step, bot_id=bot_id
                )
            ) as events:
                async for event in events:
                    if isinstance(event, (AgentCompleted, AgentPending, NextStep)):
                        ending = event
                    else:
                        yield event
            assert ending is not None
            if not isinstance(ending, NextStep):
                outcome = ending
                break
    except BaseException:
        close_turn(session, turn, step, "cancelled")
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
    reply: Completion | StreamFailure | RetryStep,
    *,
    at: TurnStep,
    bot_id: str,
) -> AgentCompleted | AgentFailed | None:
    """A step whose reply runs no tools: the turn's outcome, or `None` to run another step."""
    if isinstance(reply, RetryStep):
        return None
    if isinstance(reply, StreamFailure):
        close_turn(session, at.turn, at.step, "failed")
        return AgentFailed(reason=reply.reason)
    decision = await runtime.hooks.end_of_step(session=session)
    if isinstance(decision, GiveUp):
        close_turn(session, at.turn, at.step, "failed")
        return AgentFailed(reason=decision.reason)
    if isinstance(decision, Tell):
        _end_step_with_note(session, at.turn, at.step, decision.note)
        return None
    if await log_waiting_messages(runtime, session, turn=at.turn, bot_id=bot_id):
        session.append(StepEnd(turn=at.turn, step=at.step))
        return None
    close_turn(session, at.turn, at.step, "completed")
    return AgentCompleted(text=reply.full_text)


async def _stream_reply(
    runtime: Runtime, session: Session, bot_id: str, *, at: TurnStep
) -> AsyncIterator[TextChunk | ToolCallChunk | Completion | StreamFailure | RetryStep]:
    """A request to `bot_id`'s model: chunks, then `Completion`, `StreamFailure` or `RetryStep`."""
    choice = await runtime.models.model_for(bot_id)
    if isinstance(choice, NoModel):
        refused = StreamFailure(reason=PICK_A_MODEL)
        session.append(AssistantChunk(turn=at.turn, step=at.step, chunk=refused))
        yield refused
        return
    selected = session.tools_selected()
    specs = runtime.tools.specs(selected, sees_images=choice.has_vision) if runtime.tools else None
    context = await runtime.hooks.start_of_step()
    messages = runtime.request_messages(session, context, sees_images=choice.has_vision)
    if runtime.checkpoint is not None:
        await runtime.checkpoint(session)

    completed: Completion | None = None
    failed: StreamFailure | None = None
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
                elif isinstance(event, Completion):
                    completed = event
                elif isinstance(event, StreamFailure):
                    failed = event

        if failed is not None or completed is None:
            failure = failed if failed is not None else StreamFailure(reason=NO_TERMINAL_REASON)
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
    runtime: Runtime, session: Session, failure: StreamFailure, *, turn: int
) -> StreamFailure | RetryStep:
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
    if isinstance(event, StreamFailure) and event.images_to_hide is not None:
        return
    session.append(AssistantChunk(turn=at.turn, step=at.step, chunk=event))


def _hide_images(session: Session, failure: StreamFailure, *, turn: int) -> bool:
    """Log a hide of as many more images as `failure` asks: `True` when one more could go."""
    if failure.images_to_hide is None:
        return False
    through = hide_through_for_fewer_images(session.events(), failure.images_to_hide)
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
                isinstance(event, CompactionEnd) and event.has_summary
            ):
                shrank = True
    return shrank


def _end_step_with_note(session: Session, turn: int, step: int, note: str) -> None:
    """Close the step with a note the model reads before the next request."""
    session.append(ApplicationMessageEvent(turn=turn, message=ApplicationMessage(content=note)))
    session.append(StepEnd(turn=turn, step=step))
