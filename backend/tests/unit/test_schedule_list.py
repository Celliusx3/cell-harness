"""`schedule_list` and `schedule_view`: a bot reads back its own scheduled tasks."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness.bots import ASSISTANT_ID, BUILDER_ID, MENTION_TURN_ORDER, GroupService
from harness.schedules import ScheduleService
from harness.tools import INVALID_ARGUMENTS, Failure, Ok
from harness.tools.native.schedule import schedule_list_tool, schedule_view_tool
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.helpers import durable_service, no_bots
from tests.unit.schedule_helpers import Clock, ask, schedules_in, tick_and_settle, world

NOW = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)
HOURLY = "DTSTART:20261112T080000Z\nRRULE:FREQ=HOURLY"
DAILY = "DTSTART:20261112T060000Z\nRRULE:FREQ=DAILY"


@pytest.fixture
async def groups(tmp_path: Path) -> GroupService:
    sessions = durable_service(tmp_path / "sessions")
    found = no_bots(sessions)
    await found.open_active_bots()
    return GroupService(found, sessions, MENTION_TURN_ORDER)


@pytest.fixture
def clock() -> Clock:
    return Clock(NOW)


@pytest.fixture
def schedules(tmp_path: Path, clock: Clock) -> ScheduleService:
    return schedules_in(tmp_path, clock)


def _listed(outcome) -> dict:
    assert isinstance(outcome, Ok)
    return json.loads(outcome.text)


def _titles(listed: dict) -> list[str]:
    return [item["title"] for item in listed["items"]]


async def test_a_bot_lists_only_its_own_schedules(
    groups: GroupService, schedules: ScheduleService
) -> None:
    mine = schedules.create(ASSISTANT_ID, "Mine", "Mine.", HOURLY)
    schedules.create(BUILDER_ID, "Theirs", "Theirs.", HOURLY)

    listed = _listed(await ask(schedule_list_tool(groups, schedules)))

    assert [item["id"] for item in listed["items"]] == [mine.id]
    assert listed["items"][0]["last_occurrence_at"] is None
    assert (listed["shown"], listed["total"], listed["limit"], listed["offset"]) == (1, 1, 20, 0)


async def test_active_come_first_by_next_time_then_paused_and_ended_newest_first(
    groups: GroupService, schedules: ScheduleService, clock: Clock
) -> None:
    paused = schedules.create(ASSISTANT_ID, "Paused", "P.", HOURLY)
    schedules.pause(paused.id)
    clock.advance(timedelta(minutes=1))
    schedules.create(ASSISTANT_ID, "Daily", "D.", DAILY)
    clock.advance(timedelta(minutes=1))
    schedules.create(ASSISTANT_ID, "Hourly", "H.", HOURLY)
    clock.advance(timedelta(minutes=1))
    ended = schedules.create(ASSISTANT_ID, "Ended", "E.", HOURLY)
    schedules.end(ended.id)

    listed = _listed(await ask(schedule_list_tool(groups, schedules)))

    assert _titles(listed) == ["Hourly", "Daily", "Ended", "Paused"]


async def test_the_active_filter_picks_active_or_the_rest(
    groups: GroupService, schedules: ScheduleService
) -> None:
    schedules.create(ASSISTANT_ID, "Running", "R.", HOURLY)
    paused = schedules.create(ASSISTANT_ID, "Paused", "P.", HOURLY)
    schedules.pause(paused.id)
    tool = schedule_list_tool(groups, schedules)

    assert _titles(_listed(await ask(tool, active=True))) == ["Running"]
    assert _titles(_listed(await ask(tool, active=False))) == ["Paused"]


async def test_limit_and_offset_page_through_with_total_and_shown(
    groups: GroupService, schedules: ScheduleService, clock: Clock
) -> None:
    for n in range(5):
        schedules.create(ASSISTANT_ID, f"Task {n}", "Do it.", HOURLY)
        clock.advance(timedelta(seconds=1))

    listed = _listed(await ask(schedule_list_tool(groups, schedules), limit=2, offset=4))

    assert (listed["shown"], listed["total"], listed["limit"], listed["offset"]) == (1, 5, 2, 4)
    assert len(listed["items"]) == 1


@pytest.mark.parametrize("arguments", [{"limit": 0}, {"limit": 51}, {"offset": -1}])
async def test_a_page_out_of_bounds_is_a_typed_failure(
    groups: GroupService, schedules: ScheduleService, arguments: dict
) -> None:
    outcome = await ask(schedule_list_tool(groups, schedules), **arguments)

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS


async def test_a_view_after_a_delivery_shows_the_last_occurrence(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    clock.advance(timedelta(hours=1, seconds=30))
    await tick_and_settle(scheduler, runs, gateway)

    outcome = await ask(
        schedule_view_tool(
            GroupService(no_bots(sessions), sessions, MENTION_TURN_ORDER), schedules
        ),
        id=made.id,
    )

    shown = _listed(outcome)
    assert shown["id"] == made.id
    assert shown["last_occurrence_at"] == "2026-11-12T09:00:00Z"
    assert shown["scheduled_at"] == "2026-11-12T10:00:00Z"


async def test_another_bot_s_schedule_is_not_found(
    groups: GroupService, schedules: ScheduleService
) -> None:
    theirs = schedules.create(BUILDER_ID, "Theirs", "Theirs.", HOURLY)

    outcome = await ask(schedule_view_tool(groups, schedules), id=theirs.id)

    assert outcome == Failure(INVALID_ARGUMENTS, f"no schedule with id {theirs.id!r}")
