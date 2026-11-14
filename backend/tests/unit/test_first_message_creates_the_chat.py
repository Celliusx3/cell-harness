"""A built-in bot's chat nobody wrote in yet is created by the first message heard there."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID, BUILDER_ID
from harness.prompts import ASSISTANT_INSTRUCTIONS, BUILDER_INSTRUCTIONS
from harness.runs.service.bot_messages import BotMessenger
from harness.schedules import Scheduler
from harness.session.domain.models import (
    AssistantMessageEvent,
    BotInstructionsEvent,
    BotMessage,
    BotMessageEvent,
    ScheduleReminderEvent,
    TurnStart,
)
from harness.session.repository.session_repository import SessionNotFoundError
from harness.session.service.session_service import SessionService
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.gateway_helpers import build, settle
from tests.unit.helpers import no_bots, no_skills
from tests.unit.schedule_helpers import START, Clock, schedules_in, tick_and_settle

HOURLY = "DTSTART:20261112T080000Z\nRRULE:FREQ=HOURLY"
ASKED = BotMessage(
    from_bot_id=ASSISTANT_ID, from_name="Assistant", text="Make a bot.", hop=1, intent="request"
)


async def _is_unwritten(sessions: SessionService, tmp_path: Path, chat_id: str) -> bool:
    try:
        await sessions.read(chat_id)
    except SessionNotFoundError:
        return not (tmp_path / "sessions" / f"{chat_id}.jsonl").exists()
    return False


async def test_a_schedule_due_in_assistant_s_unwritten_chat_runs_a_turn_and_stays_active(
    tmp_path: Path,
) -> None:
    _, gateway, runs, _, sessions = await build(
        tmp_path, ScriptedClient(completed("Checked.")), skills=no_skills()
    )
    clock = Clock(START)
    schedules = schedules_in(tmp_path, clock)
    scheduler = Scheduler(schedules, no_bots(sessions), runs, follow=gateway.follow, now=clock)
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    assert await _is_unwritten(sessions, tmp_path, ASSISTANT_ID)

    clock.advance(timedelta(hours=1, seconds=30))
    await tick_and_settle(scheduler, runs, gateway)

    (kept,) = schedules.schedules()
    assert kept.status == "active"
    assert len(kept.deliveries) == 1
    events = (await sessions.read(ASSISTANT_ID)).events()
    reminders = [e for e in events if isinstance(e, ScheduleReminderEvent)]
    assert [[r.schedule_id for r in e.reminders] for e in reminders] == [[made.id]]
    assert [e.message.content for e in events if isinstance(e, AssistantMessageEvent)] == [
        "Checked."
    ]


async def test_a_bot_message_to_bot_builder_s_unwritten_chat_is_heard_and_answered(
    tmp_path: Path,
) -> None:
    _, gateway, runs, _, sessions = await build(
        tmp_path, ScriptedClient(completed("Made it.")), skills=no_skills()
    )
    messages = BotMessenger(no_bots(sessions), runs, follow=gateway.follow)
    assert await _is_unwritten(sessions, tmp_path, BUILDER_ID)

    run = await messages.deliver(BUILDER_ID, ASKED)
    await settle(runs, gateway)

    assert run is not None
    events = (await sessions.read(BUILDER_ID)).events()
    assert [e.message for e in events if isinstance(e, BotMessageEvent)] == [ASKED]
    assert [e.message.content for e in events if isinstance(e, AssistantMessageEvent)] == [
        "Made it."
    ]


@pytest.mark.parametrize(
    ("bot_id", "instructions"),
    [(ASSISTANT_ID, ASSISTANT_INSTRUCTIONS), (BUILDER_ID, BUILDER_INSTRUCTIONS)],
    ids=[ASSISTANT_ID, BUILDER_ID],
)
async def test_the_new_chat_logs_the_bot_s_instructions_before_its_first_turn(
    tmp_path: Path, bot_id: str, instructions: str
) -> None:
    _, gateway, runs, _, sessions = await build(
        tmp_path, ScriptedClient(completed("Done.")), skills=no_skills()
    )
    messages = BotMessenger(no_bots(sessions), runs, follow=gateway.follow)
    assert await _is_unwritten(sessions, tmp_path, bot_id)

    await messages.deliver(bot_id, ASKED)
    await settle(runs, gateway)

    events = (await sessions.read(bot_id)).events()
    logged = [e for e in events if isinstance(e, BotInstructionsEvent)]
    assert [(e.bot_id, e.instructions) for e in logged] == [(bot_id, instructions)]
    first_turn = next(i for i, e in enumerate(events) if isinstance(e, TurnStart))
    assert events.index(logged[0]) < first_turn


async def test_a_bot_message_for_a_bot_that_is_gone_is_dropped_and_saves_no_chat(
    tmp_path: Path,
) -> None:
    _, gateway, runs, _, sessions = await build(tmp_path, ScriptedClient([]), skills=no_skills())
    messages = BotMessenger(no_bots(sessions), runs, follow=gateway.follow)

    run = await messages.deliver("gone", ASKED)

    assert run is None
    assert await _is_unwritten(sessions, tmp_path, "gone")
