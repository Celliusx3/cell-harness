"""A goal run's rules: what starts one, who leads, the lead's decision block, and who it names."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from harness.bots.domain.models import MENTION_PATTERN, Bot, NonBlankText
from harness.groups.domain.models import Group
from harness.groups.domain.speaker_queue import lead_of
from harness.session.domain.goal import BLOCK_CLOSE, BLOCK_OPEN

GOAL_MAX_TURNS = 13
GOAL_WAIT_SECONDS = 600.0
GOAL_MAX_BUSY_WAITS = 3
GOAL_MAX_REPEATS = 3
GOAL_COMMAND = "/goal "


class GoalContinue(BaseModel):
    """The lead hands the next team turn to the member `next`, with `task`."""

    model_config = ConfigDict(frozen=True)

    status: Literal["continue"]
    next: NonBlankText
    task: NonBlankText
    detail: str | None = None


class GoalFinish(BaseModel):
    """The lead ends the run: the goal is done, needs the person, or is blocked."""

    model_config = ConfigDict(frozen=True)

    status: Literal["done", "needs_you", "blocked"]
    detail: NonBlankText


_DECISION: TypeAdapter[GoalContinue | GoalFinish] = TypeAdapter(
    Annotated[GoalContinue | GoalFinish, Field(discriminator="status")]
)


class GoalTally(NamedTuple):
    """A run's counts: team turns, waits past the limit, assignments given, the lead's note."""

    used: int = 0
    busy_waits: int = 0
    assignments: tuple[str, ...] = ()
    note: str | None = None

    def assigned(self, bot_id: str, task: str) -> GoalTally:
        """This tally with `task` given to `bot_id` once more."""
        return self._replace(assignments=(*self.assignments, assignment_key(bot_id, task)))

    def repeats(self, bot_id: str, task: str) -> int:
        """How many times `task` has been given to `bot_id`, case and spacing aside."""
        return self.assignments.count(assignment_key(bot_id, task))


def assignment_key(bot_id: str, task: str) -> str:
    """`task` for `bot_id`, the same however it is cased or spaced."""
    return f"{bot_id}:{' '.join(task.split()).casefold()}"


def goal_text(text: str) -> str | None:
    """The goal a `/goal ` message asks for; `None` for any other message or a blank goal."""
    if not text.startswith(GOAL_COMMAND):
        return None
    goal = text[len(GOAL_COMMAND) :].strip()
    return goal or None


def goal_decision(reply: str) -> GoalContinue | GoalFinish | None:
    """The last complete `<goal>` block in `reply`; `None` when it is missing or broken."""
    close = reply.rfind(BLOCK_CLOSE)
    start = reply.rfind(BLOCK_OPEN, 0, close) if close >= 0 else -1
    if start < 0:
        return None
    try:
        return _DECISION.validate_json(reply[start + len(BLOCK_OPEN) : close])
    except ValidationError:
        return None


def goal_lead(goal: str, members: Sequence[Bot], group: Group) -> Bot | None:
    """The member @named first in `goal`, else `group`'s lead, else its first member."""
    named = [(at, bot) for bot in members if (at := _mention_at(bot, goal)) is not None]
    if named:
        return min(named, key=lambda found: found[0])[1]
    return lead_of(members, group)


def goal_member(reference: str, members: Sequence[Bot], *, lead_id: str) -> Bot | None:
    """The member `reference` names by id, or by a name no other has; never the lead."""
    wanted = reference.strip().removeprefix("@").casefold()
    others = [bot for bot in members if bot.id != lead_id]
    by_id = next((bot for bot in others if bot.id.casefold() == wanted), None)
    if by_id is not None:
        return by_id
    by_name = [bot for bot in members if bot.name.strip().casefold() == wanted]
    return by_name[0] if len(by_name) == 1 and by_name[0].id != lead_id else None


def _mention_at(bot: Bot, text: str) -> int | None:
    pattern = MENTION_PATTERN.format(name=re.escape(bot.name.strip()))
    found = re.search(pattern, text, re.IGNORECASE)
    return None if found is None else found.start()
