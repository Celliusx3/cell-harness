"""Schedules due together in one chat arrive as one message; in different chats, one each."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from harness.bots import ASSISTANT_ID, BUILDER_ID
from harness.llm import UserMessage
from harness.session.domain.derive import derive_messages
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.schedule_helpers import reminder_events, tick_and_settle, world

EVERY_MINUTE = "DTSTART:20261112T080000Z\nRRULE:FREQ=MINUTELY"
HOURLY = "DTSTART:20261112T060100Z\nRRULE:FREQ=HOURLY"
EXPECTED_BATCH = (
    "[SCHEDULE REMINDER BATCH]\n"
    "This is a scheduled message from the user\n"
    'reminders_json: [{{"schedule_id": "{first}", "occurrence_at": "2026-11-12T08:01:00Z", '
    '"reminder_prompt": "Check the 日志."}}, '
    '{{"schedule_id": "{second}", "occurrence_at": "2026-11-12T08:01:00Z", '
    '"reminder_prompt": "Say \\"hi\\"."}}]'
)


async def test_two_schedules_due_together_in_one_chat_are_one_event(tmp_path: Path) -> None:
    client = ScriptedClient(completed("Done."))
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(tmp_path, client)
    first = schedules.create(ASSISTANT_ID, "Logs", "Check the 日志.", EVERY_MINUTE)
    second = schedules.create(ASSISTANT_ID, "Hi", 'Say "hi".', HOURLY)
    clock.advance(timedelta(minutes=1, seconds=30))

    await tick_and_settle(scheduler, runs, gateway)

    (event,) = await reminder_events(sessions, ASSISTANT_ID)
    assert [r.schedule_id for r in event.reminders] == [first.id, second.id]
    expected = UserMessage(content=EXPECTED_BATCH.format(first=first.id, second=second.id))
    events = (await sessions.read(ASSISTANT_ID)).events()
    assert expected in derive_messages(events)
    assert expected in client.seen
    assert all(len(s.deliveries) == 1 for s in schedules.schedules())


async def test_schedules_of_different_bots_each_run_in_their_own_chat(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    mine = schedules.create(ASSISTANT_ID, "Mine", "Mine.", EVERY_MINUTE)
    theirs = schedules.create(BUILDER_ID, "Theirs", "Theirs.", EVERY_MINUTE)
    clock.advance(timedelta(minutes=1, seconds=30))

    await tick_and_settle(scheduler, runs, gateway)

    (assistant_event,) = await reminder_events(sessions, ASSISTANT_ID)
    (builder_event,) = await reminder_events(sessions, BUILDER_ID)
    assert [r.schedule_id for r in assistant_event.reminders] == [mine.id]
    assert [r.schedule_id for r in builder_event.reminders] == [theirs.id]
