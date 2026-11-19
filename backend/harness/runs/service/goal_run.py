"""A goal run: the lead and the member it names take team turns until the lead ends it."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import aclosing
from typing import NamedTuple

from harness.bots import Bot
from harness.files import ChatFile
from harness.groups import GroupService
from harness.groups.domain.goal import GOAL_MAX_TURNS, GoalContinue, goal_decision, goal_member
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
    runtime: Runtime, groups: GroupService, session: Session, opening: GoalOpening
) -> AsyncIterator[TurnEvent]:
    """The lead's turn, then each member's it names and the lead's again, until the run ends."""
    lead = opening.lead
    session.append(
        GoalStartEvent(
            turn=session.next_turn(), goal=opening.goal, lead_id=lead.id, max_turns=GOAL_MAX_TURNS
        )
    )
    step: TeamTurn | GoalEnding = TeamTurn(lead, None)
    used = 0
    while isinstance(step, TeamTurn):
        used += 1
        groups.named_speaker(session, step.speaker.id)
        session.append(
            GoalStepEvent(
                turn=session.next_turn(),
                bot_id=step.speaker.id,
                role="lead" if step.speaker.id == lead.id else "member",
                step=used,
                task=step.task,
                note=None,
            )
        )
        terminal: TurnEvent | None = None
        async with aclosing(_turn(runtime, session, opening, step.speaker, used)) as events:
            async for event in events:
                terminal = event
                yield event
        members = groups.chat_members(session.id).bots
        step = _next_step(terminal, step.speaker, lead, members, used)
    session.append(
        GoalEndEvent(
            turn=session.next_turn() - 1, status=step.status, detail=step.detail, turns_used=used
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
    terminal: TurnEvent | None, speaker: Bot, lead: Bot, members: Sequence[Bot], used: int
) -> TeamTurn | GoalEnding:
    """After `speaker`'s turn: the lead after a member, else what the lead's block decides."""
    if not isinstance(terminal, AgentCompleted):
        if speaker.id == lead.id:
            return GoalEnding("failed", LEAD_FAILED.format(lead=lead.name))
        return GoalEnding("failed", MEMBER_FAILED.format(member=speaker.name, lead=lead.name))
    if speaker.id != lead.id:
        return TeamTurn(lead, None)
    decision = goal_decision(terminal.text)
    if decision is None:
        return GoalEnding("blocked", NO_VALID_STEP.format(lead=lead.name))
    if not isinstance(decision, GoalContinue):
        return GoalEnding(decision.status, decision.detail)
    member = goal_member(decision.next, members, lead_id=lead.id)
    if member is None:
        return GoalEnding("blocked", NOT_A_MEMBER.format(lead=lead.name, name=decision.next))
    if used >= GOAL_MAX_TURNS:
        return GoalEnding("limit_reached", LIMIT_REACHED.format(max_turns=GOAL_MAX_TURNS))
    return TeamTurn(member, decision.task)
