"""`schedule_create`: a scheduled task made from the bot's own chat, checked before it is kept."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from harness.app_events import AppEvents
from harness.bots import ASSISTANT_ID, BUILDER_ID, BotService, GroupDraft
from harness.schedules import ScheduleService
from harness.tools import INVALID_ARGUMENTS, REFUSED, Failure, Ok
from harness.tools.native.schedule import SCHEDULE_CREATE, schedule_create_tool
from harness.web.runtime import DEFAULT_TOOLS, NOT_CALLABLE_FROM_SCRIPTS, SUBAGENT_TOOLS
from tests.unit.helpers import context_for, durable_service
from tests.unit.schedule_helpers import Clock, schedules_in

CONFIG = Path(__file__).resolve().parents[2] / "config.json"
THURSDAY = datetime(2026, 11, 12, 8, 0, tzinfo=UTC)
WEEKDAYS = "DTSTART;TZID=Asia/Singapore:20260901T080000\nRRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"


@pytest.fixture
def bots(tmp_path: Path) -> BotService:
    return BotService(
        tmp_path / "bots.json",
        durable_service(tmp_path / "sessions"),
        assistant_instructions="A.",
        events=AppEvents(),
    )


@pytest.fixture
def schedules(tmp_path: Path) -> ScheduleService:
    return schedules_in(tmp_path, Clock(THURSDAY))


async def call(
    bots: BotService, schedules: ScheduleService, chat_id: str = ASSISTANT_ID, **arguments: str
):
    await bots.active_bots()
    tool = schedule_create_tool(bots, schedules)
    context = context_for(bot_id=ASSISTANT_ID, conversation_id=chat_id)
    return await tool.invoke(json.dumps(arguments), context=context)


async def test_a_schedule_made_in_chat_is_kept_and_says_when_it_runs_next(
    bots: BotService, schedules: ScheduleService
) -> None:
    outcome = await call(
        bots, schedules, title="Check the deployment", prompt=" Check it. ", rrule=WEEKDAYS
    )

    assert isinstance(outcome, Ok)
    (kept,) = schedules.schedules()
    assert json.loads(outcome.text) == {
        "id": kept.id,
        "title": "Check the deployment",
        "prompt": "Check it.",
        "rrule": WEEKDAYS,
        "status": "active",
        "scheduled_at": "2026-11-13T00:00:00Z",
        "scheduled_at_local": "2026-11-13T08:00:00+08:00",
    }
    assert (kept.bot_id, kept.status) == (ASSISTANT_ID, "active")
    assert kept.scheduled_at == datetime(2026, 11, 13, tzinfo=UTC)
    assert kept.created_at == kept.updated_at == THURSDAY
    assert kept.deliveries == ()


@pytest.mark.parametrize(
    "rrule",
    [
        "RRULE:FREQ=DAILY;COUNT=1",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=SECONDLY",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY;COUNT=1001",
        "DTSTART:20261112T080000Z\nRRULE:FREQ=DAILY;COUNT=2;UNTIL=20261201T000000Z",
        "DTSTART;TZID=Mars/Olympus:20261112T080000\nRRULE:FREQ=DAILY",
        "DTSTART:20261112T080000\nRRULE:FREQ=DAILY",
    ],
)
async def test_a_bad_rrule_is_a_typed_failure_and_nothing_is_kept(
    bots: BotService, schedules: ScheduleService, rrule: str
) -> None:
    outcome = await call(bots, schedules, title="Remind me", prompt="Remind me.", rrule=rrule)

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert outcome.message.startswith("rrule: ")
    assert schedules.schedules() == ()


async def test_a_rule_with_no_occurrence_after_now_is_refused(
    bots: BotService, schedules: ScheduleService
) -> None:
    past = "DTSTART:20260101T000000Z\nRRULE:FREQ=DAILY;COUNT=1"

    outcome = await call(bots, schedules, title="Remind me", prompt="Remind me.", rrule=past)

    assert outcome == Failure(INVALID_ARGUMENTS, "rrule: no occurrence after now")
    assert schedules.schedules() == ()


@pytest.mark.parametrize(
    ("title", "prompt"), [("  ", "Remind me."), ("x" * 121, "Remind me."), ("Remind me", " ")]
)
async def test_a_blank_or_long_title_or_a_blank_prompt_is_refused(
    bots: BotService, schedules: ScheduleService, title: str, prompt: str
) -> None:
    outcome = await call(bots, schedules, title=title, prompt=prompt, rrule=WEEKDAYS)

    assert isinstance(outcome, Failure)
    assert outcome.code == INVALID_ARGUMENTS
    assert schedules.schedules() == ()


async def test_a_schedule_asked_for_in_a_group_chat_is_refused(
    bots: BotService, schedules: ScheduleService
) -> None:
    draft = GroupDraft(name="Launch", member_ids=(ASSISTANT_ID, BUILDER_ID))
    group = await bots.create_group(draft)

    outcome = await call(
        bots, schedules, group.id, title="Remind me", prompt="Remind me.", rrule=WEEKDAYS
    )

    assert outcome == Failure(REFUSED, "schedules work only in your own chat, not in a group chat")
    assert schedules.schedules() == ()


def test_schedule_create_is_offered_to_bots_but_not_to_scripts_or_subagents() -> None:
    approval_tools = json.loads(CONFIG.read_text())["approval"]["tools"]

    assert SCHEDULE_CREATE in DEFAULT_TOOLS
    assert SCHEDULE_CREATE in NOT_CALLABLE_FROM_SCRIPTS
    assert SCHEDULE_CREATE not in SUBAGENT_TOOLS
    assert SCHEDULE_CREATE not in approval_tools
