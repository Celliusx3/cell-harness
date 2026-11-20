"""A goal run: the lead and the member it names take team turns until the lead ends it."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing
from typing import NamedTuple

from harness.bots import Bot
from harness.files import ChatFile
from harness.groups import GroupService
from harness.groups.domain.goal import (
    GOAL_MAX_BUSY_WAITS,
    GOAL_MAX_REPEATS,
    GOAL_MAX_TURNS,
    GoalContinue,
    GoalTally,
    goal_decision,
    goal_member,
)
from harness.groups.domain.prompts import GOAL_BUSY
from harness.runs.service.goal_wait import TeamTurnEnd, team_turn
from harness.runs.service.report_inbox import ReportInbox, ReportInboxes
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.domain.goal import GoalEndEvent, GoalStatus
from harness.session.domain.log import Session
from harness.session.domain.models import GoalStartEvent, GoalStepEvent

NO_VALID_STEP = "{lead} did not give a valid next step."
NOT_A_MEMBER = "{lead} handed the next turn to {name}, who is not an active member of this group."
LIMIT_REACHED = "Paused at the {max_turns}-turn limit. Send the goal again to continue."
LEAD_FAILED = "{lead} could not finish its turn."
MEMBER_FAILED = "{member} could not return a result to {lead}."
STAYED_BUSY = "Members stayed busy past the wait limit {times} times."
REPEATED = "The team repeated the same assignment three times without finishing."
STOPPED = "Stopped by you."


class GoalOpening(NamedTuple):
    """The person's `/goal` message as typed, its files, the goal it asks for, and its lead."""

    text: str
    files: tuple[ChatFile, ...]
    goal: str
    lead: Bot


class TeamTurn(NamedTuple):
    """The next team turn: whose it is, and the member's task."""

    speaker: Bot
    task: str | None


class GoalEnding(NamedTuple):
    """How the run ends, and why."""

    status: GoalStatus
    detail: str


async def goal_run(
    runtime: Runtime,
    groups: GroupService,
    inboxes: ReportInboxes,
    session: Session,
    opening: GoalOpening,
) -> AsyncIterator[TurnEvent]:
    """The lead's turn, then each member's it names and the lead's again, until the run ends."""
    session.append(
        GoalStartEvent(
            turn=session.next_turn(),
            goal=opening.goal,
            lead_id=opening.lead.id,
            max_turns=GOAL_MAX_TURNS,
        )
    )
    with inboxes.opened(session.id) as inbox:
        async with aclosing(_team_turns(runtime, groups, inbox, session, opening)) as events:
            async for event in events:
                yield event


async def _team_turns(
    runtime: Runtime,
    groups: GroupService,
    inbox: ReportInbox,
    session: Session,
    opening: GoalOpening,
) -> AsyncIterator[TurnEvent]:
    """Each team turn, its workers' reports heard in it, then how the run ended, logged."""
    lead = opening.lead
    step: TeamTurn | GoalEnding = TeamTurn(lead, None)
    tally = GoalTally()
    try:
        while isinstance(step, TeamTurn):
            tally = tally._replace(used=tally.used + 1)
            is_lead = step.speaker.id == lead.id
            groups.named_speaker(session, step.speaker.id)
            logged = GoalStepEvent(
                turn=session.next_turn(),
                bot_id=step.speaker.id,
                role="lead" if is_lead else "member",
                step=tally.used,
                task=step.task,
                note=tally.note if is_lead else None,
            )
            tally = tally._replace(note=None) if is_lead else tally
            ended = TeamTurnEnd()
            first = _turn(runtime, session, opening, step.speaker, tally.used)
            async with aclosing(team_turn(runtime, session, inbox, logged, first, ended)) as events:
                async for event in events:
                    yield event
            members = groups.chat_members(session.id).bots
            step, tally = _next_step(ended, step.speaker, lead, members, tally)
    except (asyncio.CancelledError, GeneratorExit):
        _log_end(session, GoalEnding("stopped", STOPPED), tally.used)
        raise
    _log_end(session, step, tally.used)


def _log_end(session: Session, ending: GoalEnding, turns_used: int) -> None:
    """Log how the run ended, in its last turn."""
    session.append(
        GoalEndEvent(
            turn=session.next_turn() - 1,
            status=ending.status,
            detail=ending.detail,
            turns_used=turns_used,
        )
    )


def _turn(
    runtime: Runtime, session: Session, opening: GoalOpening, speaker: Bot, used: int
) -> AsyncIterator[TurnEvent]:
    """The first team turn answers the person's message; every later one speaks on."""
    if used == 1:
        return runtime.run(opening.text, session=session, bot_id=speaker.id, files=opening.files)
    return runtime.speak(session=session, bot_id=speaker.id)


def _next_step(
    ended: TeamTurnEnd, speaker: Bot, lead: Bot, members: Sequence[Bot], tally: GoalTally
) -> tuple[TeamTurn | GoalEnding, GoalTally]:
    """After `speaker`'s team turn: an ending, the lead after a member, else the lead's decision."""
    if not isinstance(ended.terminal, AgentCompleted):
        if speaker.id == lead.id:
            return GoalEnding("failed", LEAD_FAILED.format(lead=lead.name)), tally
        failed = MEMBER_FAILED.format(member=speaker.name, lead=lead.name)
        return GoalEnding("failed", failed), tally
    if ended.question is not None:
        return GoalEnding("needs_you", ended.question), tally
    if ended.busy:
        tally = tally._replace(
            busy_waits=tally.busy_waits + 1, note=GOAL_BUSY.format(member=speaker.name)
        )
        if tally.busy_waits >= GOAL_MAX_BUSY_WAITS:
            return GoalEnding("blocked", STAYED_BUSY.format(times=tally.busy_waits)), tally
    if speaker.id != lead.id:
        return TeamTurn(lead, None), tally
    return _lead_decides(ended.terminal.text, lead, members, tally)


def _lead_decides(
    reply: str, lead: Bot, members: Sequence[Bot], tally: GoalTally
) -> tuple[TeamTurn | GoalEnding, GoalTally]:
    """What the lead's block in `reply` decides: an ending, or the member it names and the task."""
    decision = goal_decision(reply)
    if decision is None:
        return GoalEnding("blocked", NO_VALID_STEP.format(lead=lead.name)), tally
    if not isinstance(decision, GoalContinue):
        return GoalEnding(decision.status, decision.detail), tally
    member = goal_member(decision.next, members, lead_id=lead.id)
    if member is None:
        ending = NOT_A_MEMBER.format(lead=lead.name, name=decision.next)
        return GoalEnding("blocked", ending), tally
    if tally.used >= GOAL_MAX_TURNS:
        return GoalEnding("limit_reached", LIMIT_REACHED.format(max_turns=GOAL_MAX_TURNS)), tally
    tally = tally.assigned(member.id, decision.task)
    if tally.repeats(member.id, decision.task) >= GOAL_MAX_REPEATS:
        return GoalEnding("blocked", REPEATED), tally
    return TeamTurn(member, decision.task), tally
