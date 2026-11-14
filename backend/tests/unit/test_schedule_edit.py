"""`schedule_edit`: a bot changes, pauses, resumes or deletes one of its own scheduled tasks."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from harness.app_events import AppEventService
from harness.bots import (
    ASSISTANT_ID,
    BUILDER_ID,
    BotRepository,
    BotService,
    GroupDraft,
    GroupService,
)
from harness.schedules import ScheduleService
from harness.session.service.session_service import SessionService
from harness.tools import INVALID_ARGUMENTS, REFUSED, Failure, Ok
from harness.tools.native.schedule import (
    SCHEDULE_EDIT,
    SCHEDULE_LIST,
    SCHEDULE_VIEW,
    schedule_edit_tool,
    schedule_list_tool,
    schedule_view_tool,
)
from harness.web.runtime import DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS, SUBAGENT_TOOLS
from tests.unit.fakes import ScriptedClient, completed
from tests.unit.group_helpers import group_service, groups_in
from tests.unit.helpers import durable_service, no_bots
from tests.unit.schedule_helpers import (
    Clock,
    ask,
    reminder_events,
    schedules_in,
    tick_and_settle,
    world,
)

CONFIG = Path(__file__).resolve().parents[2] / "config.json"
NOW = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)
HOURLY = "DTSTART:20261112T080000Z\nRRULE:FREQ=HOURLY"
DAILY = "DTSTART:20261112T060000Z\nRRULE:FREQ=DAILY"
ONE_OFF = "DTSTART:20261112T081000Z\nRRULE:FREQ=DAILY;COUNT=1"


@pytest.fixture
def sessions(tmp_path: Path) -> SessionService:
    return durable_service(tmp_path / "sessions")


@pytest.fixture
def bots(tmp_path: Path, sessions: SessionService) -> BotService:
    return BotService(
        BotRepository(tmp_path / "bots.json"),
        sessions,
        assistant_instructions="A.",
        app_events=AppEventService(),
    )


@pytest.fixture
async def groups(tmp_path: Path, bots: BotService, sessions: SessionService) -> GroupService:
    return groups_in(tmp_path, bots, sessions, AppEventService())


@pytest.fixture
def clock() -> Clock:
    return Clock(NOW)


@pytest.fixture
def schedules(tmp_path: Path, clock: Clock) -> ScheduleService:
    return schedules_in(tmp_path, clock)


async def edit(groups: GroupService, schedules: ScheduleService, **arguments: object):
    return await ask(schedule_edit_tool(groups, schedules), **arguments)


async def test_pausing_stops_a_due_run(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)

    paused = await ask(
        schedule_edit_tool(group_service(no_bots(sessions), sessions), schedules),
        id=made.id,
        action="update",
        active=False,
    )
    clock.advance(timedelta(hours=2))
    await tick_and_settle(scheduler, runs, gateway)

    assert isinstance(paused, Ok)
    assert json.loads(paused.text)["status"] == "paused"
    assert await reminder_events(sessions, ASSISTANT_ID) == []


async def test_resuming_runs_at_the_next_time_after_the_edit(tmp_path: Path) -> None:
    _, gateway, runs, sessions, clock, schedules, scheduler = await world(
        tmp_path, ScriptedClient(completed("Done."))
    )
    tool = schedule_edit_tool(group_service(no_bots(sessions), sessions), schedules)
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    await ask(tool, id=made.id, action="update", active=False)
    clock.advance(timedelta(hours=2, minutes=30))

    resumed = await ask(tool, id=made.id, action="update", active=True)
    await tick_and_settle(scheduler, runs, gateway)
    assert await reminder_events(sessions, ASSISTANT_ID) == []
    clock.advance(timedelta(minutes=31))
    await tick_and_settle(scheduler, runs, gateway)

    assert isinstance(resumed, Ok)
    assert json.loads(resumed.text)["scheduled_at"] == "2026-11-12T11:00:00Z"
    (event,) = await reminder_events(sessions, ASSISTANT_ID)
    assert [r.occurrence_at for r in event.reminders] == [datetime(2026, 11, 12, 11, tzinfo=UTC)]


async def test_resuming_with_no_occurrence_left_is_a_typed_failure(
    groups: GroupService, bots: BotService, schedules: ScheduleService, clock: Clock
) -> None:
    made = schedules.create(ASSISTANT_ID, "Once", "Once.", ONE_OFF)
    schedules.pause(made.id)
    clock.advance(timedelta(hours=1))

    outcome = await edit(groups, schedules, id=made.id, action="update", active=True)

    assert outcome == Failure(INVALID_ARGUMENTS, "rrule: no occurrence after now")
    assert schedules.get(made.id).status == "paused"


async def test_a_new_rrule_moves_scheduled_at(
    groups: GroupService, bots: BotService, schedules: ScheduleService, clock: Clock
) -> None:
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    clock.advance(timedelta(minutes=5))

    outcome = await edit(groups, schedules, id=made.id, action="update", rrule=DAILY)

    assert isinstance(outcome, Ok)
    kept = schedules.get(made.id)
    assert (kept.rrule, kept.status) == (DAILY, "active")
    assert kept.scheduled_at == datetime(2026, 11, 13, 6, tzinfo=UTC)
    assert kept.updated_at == clock.at


async def test_a_new_rrule_on_an_ended_schedule_makes_it_active(
    groups: GroupService, bots: BotService, schedules: ScheduleService
) -> None:
    made = schedules.create(ASSISTANT_ID, "Once", "Once.", ONE_OFF)
    schedules.end(made.id)

    outcome = await edit(groups, schedules, id=made.id, action="update", rrule=HOURLY)

    assert isinstance(outcome, Ok)
    assert json.loads(outcome.text)["status"] == "active"
    assert schedules.get(made.id).scheduled_at == datetime(2026, 11, 12, 9, tzinfo=UTC)


async def test_a_bad_new_rrule_is_a_typed_failure_and_nothing_changes(
    groups: GroupService, bots: BotService, schedules: ScheduleService
) -> None:
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)

    outcome = await edit(groups, schedules, id=made.id, action="update", rrule="RRULE:FREQ=DAILY")

    assert isinstance(outcome, Failure)
    assert outcome.message.startswith("rrule: ")
    assert schedules.get(made.id) == made


async def test_a_title_only_update_keeps_scheduled_at(
    groups: GroupService, bots: BotService, schedules: ScheduleService, clock: Clock
) -> None:
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    clock.advance(timedelta(minutes=5))

    outcome = await edit(groups, schedules, id=made.id, action="update", title=" Look in ")

    assert isinstance(outcome, Ok)
    kept = schedules.get(made.id)
    assert (kept.title, kept.prompt, kept.status) == ("Look in", "Check in.", "active")
    assert kept.scheduled_at == made.scheduled_at
    assert kept.updated_at == clock.at


async def test_a_blank_prompt_is_refused_with_its_field(
    groups: GroupService, bots: BotService, schedules: ScheduleService
) -> None:
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)

    outcome = await edit(groups, schedules, id=made.id, action="update", prompt=" ")

    assert outcome == Failure(INVALID_ARGUMENTS, "prompt: must not be empty")


async def test_delete_removes_it(
    groups: GroupService, bots: BotService, schedules: ScheduleService
) -> None:
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)
    kept = schedules.create(ASSISTANT_ID, "Keep", "Keep.", HOURLY)

    outcome = await edit(groups, schedules, id=made.id, action="delete")

    assert outcome == Ok(json.dumps({"id": made.id, "deleted": True}))
    assert schedules.schedules() == (kept,)


async def test_an_empty_update_is_a_typed_failure(
    groups: GroupService, bots: BotService, schedules: ScheduleService
) -> None:
    made = schedules.create(ASSISTANT_ID, "Check in", "Check in.", HOURLY)

    outcome = await edit(groups, schedules, id=made.id, action="update")

    assert outcome == Failure(
        INVALID_ARGUMENTS, "update needs at least one of title, prompt, rrule, active"
    )


@pytest.mark.parametrize("action", ["update", "delete"])
async def test_an_unknown_or_another_bot_s_id_is_a_typed_failure(
    groups: GroupService, bots: BotService, schedules: ScheduleService, action: str
) -> None:
    theirs = schedules.create(BUILDER_ID, "Theirs", "Theirs.", HOURLY)

    unknown = await edit(groups, schedules, id="nope", action=action, title="X")
    other = await edit(groups, schedules, id=theirs.id, action=action, title="X")

    assert unknown == Failure(INVALID_ARGUMENTS, "no schedule with id 'nope'")
    assert other == Failure(INVALID_ARGUMENTS, f"no schedule with id {theirs.id!r}")
    assert schedules.schedules() == (theirs,)


@pytest.mark.parametrize(
    ("make", "arguments"),
    [
        (schedule_list_tool, {}),
        (schedule_view_tool, {"id": "any"}),
        (schedule_edit_tool, {"id": "any", "action": "delete"}),
    ],
)
async def test_every_tool_is_refused_in_a_group_chat(
    groups: GroupService, bots: BotService, schedules: ScheduleService, make, arguments: dict
) -> None:
    group = await groups.create(GroupDraft(name="Launch", member_ids=(ASSISTANT_ID, BUILDER_ID)))

    outcome = await ask(make(groups, schedules), group.id, **arguments)

    assert outcome == Failure(REFUSED, "schedules work only in your own chat, not in a group chat")


def test_the_tools_are_offered_to_bots_but_not_to_scripts_or_subagents() -> None:
    approval_tools = json.loads(CONFIG.read_text())["approval"]["tools"]

    for name in (SCHEDULE_LIST, SCHEDULE_VIEW, SCHEDULE_EDIT):
        assert name in DEFAULT_TOOLS
        assert name in NOT_CALLABLE_FROM_SCRIPTS
        assert name not in SUBAGENT_TOOLS
        assert name not in approval_tools
