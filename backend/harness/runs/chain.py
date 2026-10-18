"""A discussion: the turn that opens it, then each member the line says is next, as one run."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing

from harness.bots import Bot, BotService, ChatMembers, bot_instructions_event, group_members_event
from harness.bots.discussion import next_speaker
from harness.runtime.events import AgentCompleted, TurnEvent
from harness.runtime.service import Runtime
from harness.session.log import Session


def log_speaker(session: Session, members: ChatMembers, bot: Bot) -> None:
    """Log `bot`'s instructions, and in a group its members, where they differ from the last."""
    logged = session.bot_instructions(bot.id)
    if logged is None or (logged.name, logged.instructions) != (bot.name, bot.instructions):
        session.append(bot_instructions_event(bot))
    if members.group is not None:
        members_now = group_members_event(members.group, members.bots)
        if session.group_members() != members_now:
            session.append(members_now)


async def discussion(
    runtime: Runtime, bots: BotService, session: Session, opening: AsyncIterator[TurnEvent]
) -> AsyncIterator[TurnEvent]:
    """`opening`'s events, then each next speaker's, until nobody is next or a turn stops short."""
    turn: AsyncIterator[TurnEvent] | None = opening
    while turn is not None:
        terminal: TurnEvent | None = None
        async with aclosing(turn) as events:
            async for event in events:
                terminal = event
                yield event
        turn = _next_turn(runtime, bots, session) if isinstance(terminal, AgentCompleted) else None


def _next_turn(
    runtime: Runtime, bots: BotService, session: Session
) -> AsyncIterator[TurnEvent] | None:
    """The next speaker's turn, its instructions logged first; `None` when nobody is next."""
    members = bots.members_of_chat(session.id)
    speaker = next_speaker(session.events(), members.bots)
    if speaker is None:
        return None
    log_speaker(session, members, speaker)
    return runtime.speak(session=session, bot_id=speaker.id)
