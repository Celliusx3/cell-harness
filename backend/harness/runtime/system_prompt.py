"""The system message: the speaker's instructions and notes, the runtime's, servers'."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from harness.groups.domain.prompts import GOAL_LAST_TURN, GOAL_LEAD, GOAL_MEMBER, GOAL_NOTE
from harness.prompts import GROUP_NOTE, GROUP_WORKSPACE_NOTE, WORKSPACE_NOTE
from harness.session.domain.log import Session
from harness.session.domain.models import (
    GoalStartEvent,
    GoalStepEvent,
    GroupMembersEvent,
    SessionEvent,
    TurnStart,
    WorkspaceEvent,
)


class GoalTurn(NamedTuple):
    """The goal run a turn belongs to, and the team turn it is."""

    start: GoalStartEvent
    step: GoalStepEvent


def system_text(session: Session, guidance: str) -> str:
    """The speaker's prompt, its workspace, then each server's last logged instructions."""
    servers = (text for text in session.server_instructions().values() if text)
    workspace = _workspace_note(session.workspace_of(session.speaker_id()))
    parts = (_speaker_text(session, guidance), _goal_note(session), workspace, *servers)
    return "\n\n".join(part for part in parts if part)


def _workspace_note(named: WorkspaceEvent | None) -> str:
    """What the speaker is told of where it works; nothing when no workspace was logged."""
    if named is None:
        return ""
    if named.own_workspace is None:
        return WORKSPACE_NOTE.format(workspace=named.workspace)
    return GROUP_WORKSPACE_NOTE.format(workspace=named.workspace, own=named.own_workspace)


def _speaker_text(session: Session, guidance: str) -> str:
    """The speaker's last logged instructions, the group note in a group, then `guidance`."""
    logged = session.bot_instructions(session.speaker_id())
    if logged is None:
        return guidance
    group = session.group_members()
    note = "" if group is None else _group_note(group, logged.name)
    return " ".join(part for part in (logged.instructions, note, guidance) if part)


def _group_note(group: GroupMembersEvent, name: str) -> str:
    """What `name` is told about its group; nothing when no other member is left in it."""
    members = group.members
    at = members.index(name) if name in members else len(members)
    others = (*members[:at], *members[at + 1 :])
    if not others:
        return ""
    return GROUP_NOTE.format(name=name, group=group.name, others=_spoken_list(others))


def _spoken_list(names: tuple[str, ...]) -> str:
    """`A`, `A and B`, `A, B and C`."""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _goal_note(session: Session) -> str:
    """What the speaker is told of the goal run this turn is a team turn of; else nothing."""
    goal = _goal_turn(session.events())
    if goal is None:
        return ""
    start, step = goal
    if step.role == "member":
        lead = session.bot_instructions(start.lead_id)
        return GOAL_MEMBER.format(
            lead=start.lead_id if lead is None else lead.name,
            goal=start.goal,
            task=step.task,
            step=step.step,
            max_turns=start.max_turns,
        )
    return _lead_note(session, start, step)


def _lead_note(session: Session, start: GoalStartEvent, step: GoalStepEvent) -> str:
    """The lead's instructions for team turn `step`, with the turns left and any note."""
    group = session.group_members()
    lead = session.bot_instructions(start.lead_id)
    names = () if group is None else group.members
    others = tuple(name for name in names if lead is None or name != lead.name)
    remaining = start.max_turns - step.step
    return GOAL_LEAD.format(
        goal=start.goal,
        members=", ".join(others),
        step=step.step,
        max_turns=start.max_turns,
        remaining=remaining,
        last_turn=GOAL_LAST_TURN if remaining <= 0 else "",
        note="" if step.note is None else GOAL_NOTE.format(note=step.note),
    )


def _goal_turn(events: Sequence[SessionEvent]) -> GoalTurn | None:
    """The goal run and team turn logged for the last turn opened; `None` for no team turn."""
    start: GoalStartEvent | None = None
    step: GoalStepEvent | None = None
    turn: int | None = None
    for event in events:
        if isinstance(event, GoalStartEvent):
            start = event
        elif isinstance(event, GoalStepEvent):
            step = event
        elif isinstance(event, TurnStart):
            turn = event.turn
    if start is None or step is None or step.turn != turn:
        return None
    return GoalTurn(start, step)
