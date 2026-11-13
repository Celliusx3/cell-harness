"""A schedule falls due: its bot's own chat hears it, and the linked chat apps hear the reply."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID
from harness.llm import UserMessage
from harness.runs.service.bot_messages import hop_of_last_turn
from harness.session.derive import derive_messages
from harness.session.domain.models import (
    BotMessage,
    BotMessageEvent,
    ScheduleReminder,
    ScheduleReminderEvent,
    TurnStart,
)
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.gateway_helpers import CHAT, settle
from tests.unit.schedule_helpers import tick_and_settle, world

NOW = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)
ONE_OFF = "DTSTART:20261112T080100Z\nRRULE:FREQ=DAILY;COUNT=1"
HOURLY = "DTSTART:20261112T080000Z\nRRULE:FREQ=HOURLY"
EXPECTED_REMINDER = (
    "[SCHEDULE REMINDER]\n"
    "This is a scheduled message from the user\n"
    'schedule_id_json: "{id}"\n'
    "occurrence_at: 2026-11-12T08:01:00Z\n"
    'reminder_prompt_json: "Say \\"hi\\"."'
)


async def test_a_one_off_fires_once_in_the_bot_s_chat_and_then_ends(tmp_path: Path) -> None:
    client = ScriptedClient(completed("Hi."))
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(tmp_path, client)
    made = schedules.create(ASSISTANT_ID, "Say hi", 'Say "hi".', ONE_OFF)

    await tick_and_settle(scheduler, runs, gateway)
    assert schedules.schedules() == (made,)
    clock.advance(timedelta(minutes=2))
    await tick_and_settle(scheduler, runs, gateway)
    await tick_and_settle(scheduler, runs, gateway)

    events = (await sessions.read(ASSISTANT_ID)).events()
    reminders = [e for e in events if isinstance(e, ScheduleReminderEvent)]
    assert [[r.schedule_id for r in e.reminders] for e in reminders] == [[made.id]]
    expected = UserMessage(content=EXPECTED_REMINDER.format(id=made.id))
    assert expected in derive_messages(events)
    assert expected in client.seen
    (ended,) = schedules.schedules()
    assert ended.status == "ended"
    assert ended.scheduled_at == made.scheduled_at
    (delivery,) = ended.deliveries
    assert delivery.scheduled_at == datetime(2026, 11, 12, 8, 1, tzinfo=UTC)
    assert delivery.delivered_at == clock.at


async def test_the_reply_reaches_the_linked_chat_app_once(tmp_path: Path) -> None:
    bot, gateway, runs, _, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Hi."))
    )
    schedules.create(ASSISTANT_ID, "Say hi", "Say hi.", ONE_OFF)

    clock.advance(timedelta(minutes=2))
    await tick_and_settle(scheduler, runs, gateway)

    assert bot.sent == [(CHAT, "Hi.")]


async def test_a_repeating_schedule_moves_on_to_its_next_occurrence(tmp_path: Path) -> None:
    _, gateway, runs, _, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    assert made.scheduled_at == datetime(2026, 11, 12, 9, tzinfo=UTC)

    clock.advance(timedelta(hours=1, seconds=30))
    await tick_and_settle(scheduler, runs, gateway)

    (moved,) = schedules.schedules()
    assert moved.status == "active"
    assert moved.scheduled_at == datetime(2026, 11, 12, 10, tzinfo=UTC)
    assert len(moved.deliveries) == 1


async def test_a_schedule_whose_bot_is_gone_is_ended(tmp_path: Path) -> None:
    _, gateway, runs, _, clock, schedules, scheduler = await world(tmp_path, ScriptedClient([]))
    schedules.create("gone", "Check in", "Check in.", HOURLY)

    clock.advance(timedelta(hours=2))
    await tick_and_settle(scheduler, runs, gateway)

    (ended,) = schedules.schedules()
    assert ended.status == "ended"
    assert ended.deliveries == ()


async def test_the_loop_delivers_what_falls_due_until_it_is_closed(tmp_path: Path) -> None:
    _, gateway, runs, _, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Hi."))
    )
    scheduler.start()
    await asyncio.sleep(0)
    schedules.create(ASSISTANT_ID, "Say hi", "Say hi.", ONE_OFF)
    clock.advance(timedelta(minutes=2))
    schedules.changed.set()
    for _ in range(300):
        if schedules.schedules()[0].status == "ended":
            break
        await asyncio.sleep(0.01)
    await settle(runs, gateway)

    await scheduler.aclose()
    await scheduler.aclose()
    assert len(schedules.schedules()[0].deliveries) == 1


def test_a_turn_a_schedule_opens_is_hop_zero() -> None:
    asked = BotMessage(from_bot_id="r", from_name="R", text="Hi.", hop=4, intent="request")
    reminder = ScheduleReminder(schedule_id="s", title="T", prompt="P", occurrence_at=NOW)

    events = [
        TurnStart(turn=0, bot_id="a"),
        BotMessageEvent(turn=0, message=asked),
        TurnStart(turn=1, bot_id="a"),
        ScheduleReminderEvent(turn=1, reminders=(reminder,)),
    ]

    assert hop_of_last_turn(events) == 0
