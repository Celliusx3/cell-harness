"""Auto: one call to a group's model picks who answers a message, and the lead when it is unsure."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from harness.bots import Bot
from harness.groups import Group
from harness.groups.domain.speaker_queue import lead_of
from harness.llm import UserMessage
from harness.prompts import AUTO_PICK, NO_RECENT_LINES
from harness.runtime.models import BotModels, NoModel
from harness.session.domain.log import Session
from harness.session.domain.models import (
    AssistantMessageEvent,
    GroupAutoPickEvent,
    SessionEvent,
    TurnStart,
    UserMessageEvent,
)
from harness.tools import Failure
from harness.tools.native.ask import model_reply

logger = logging.getLogger("harness.runs.auto_pick")

AUTO_PICK_TIMEOUT_SECONDS = 10.0
SURE_ENOUGH = 0.6
EVERYONE = "everyone"
RECENT_LINES = 6
LINE_CHARS = 300
INSTRUCTIONS_CHARS = 160
MESSAGE_CHARS = 4000
PERSON = "person"
UNKNOWN_SPEAKER = "a member"


class AutoPickAnswer(BaseModel):
    """The model's answer: a member's name or `everyone`, and how sure it is."""

    model_config = ConfigDict(frozen=True)

    pick: str
    confidence: float = Field(ge=0, le=1)


async def auto_pick(
    models: BotModels, session: Session, group: Group, members: Sequence[Bot], text: str
) -> GroupAutoPickEvent:
    """Who answers `text`: the model's sure pick, else the lead on any doubt or failure."""
    try:
        async with asyncio.timeout(AUTO_PICK_TIMEOUT_SECONDS):
            answer = await _answer(models, session, group, members, text)
    except Exception:
        logger.exception("Auto could not pick who answers in group %s", group.id)
        answer = None
    return _pick_event(session.next_turn(), answer, members, group)


async def _answer(
    models: BotModels, session: Session, group: Group, members: Sequence[Bot], text: str
) -> AutoPickAnswer | None:
    """The model's parsed answer; `None` when no model is saved or the call failed."""
    choice = NoModel() if group.auto_model is None else await models.model_named(group.auto_model)
    if isinstance(choice, NoModel):
        logger.warning("group %s is on Auto with no saved model %s", group.id, group.auto_model)
        return None
    question = AUTO_PICK.format(
        group=group.name,
        members="\n".join(
            f"- {bot.name}: {_clip(bot.instructions, INSTRUCTIONS_CHARS)}" for bot in members
        ),
        recent="\n".join(_recent_lines(session.events(), members)) or NO_RECENT_LINES,
        message=_clip(text, MESSAGE_CHARS),
    )
    reply = await model_reply(choice, UserMessage(content=question))
    if isinstance(reply, Failure):
        logger.warning("Auto's call failed in group %s: %s", group.id, reply.message)
        return None
    start, end = reply.text.find("{"), reply.text.rfind("}")
    return AutoPickAnswer.model_validate_json(reply.text[start : end + 1])


def _pick_event(
    turn: int, answer: AutoPickAnswer | None, members: Sequence[Bot], group: Group
) -> GroupAutoPickEvent:
    """The event for `answer`: its pick when sure and known, else the lead marked a fallback."""
    confidence = 0.0 if answer is None else answer.confidence
    if answer is not None and confidence >= SURE_ENOUGH:
        name = answer.pick.strip().casefold()
        if name == EVERYONE:
            return GroupAutoPickEvent(turn=turn, bot_id=None, confidence=confidence, fallback=False)
        named = next((bot for bot in members if bot.name.casefold() == name), None)
        if named is not None:
            return GroupAutoPickEvent(
                turn=turn, bot_id=named.id, confidence=confidence, fallback=False
            )
    lead = lead_of(members, group)
    lead_id = None if lead is None else lead.id
    return GroupAutoPickEvent(turn=turn, bot_id=lead_id, confidence=confidence, fallback=True)


def _recent_lines(events: Sequence[SessionEvent], members: Sequence[Bot]) -> list[str]:
    """The chat's last lines, oldest first: the person's messages and the members' replies."""
    names = {bot.id: bot.name for bot in members}
    speaker = UNKNOWN_SPEAKER
    lines: list[str] = []
    for event in events:
        if isinstance(event, TurnStart):
            speaker = names.get(event.bot_id or "", UNKNOWN_SPEAKER)
        elif isinstance(event, UserMessageEvent):
            lines.append(f"{PERSON}: {_clip(event.message.content, LINE_CHARS)}")
        elif isinstance(event, AssistantMessageEvent) and event.message.content.strip():
            lines.append(f"{speaker}: {_clip(event.message.content, LINE_CHARS)}")
    return lines[-RECENT_LINES:]


def _clip(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[: limit - 1]}…"
