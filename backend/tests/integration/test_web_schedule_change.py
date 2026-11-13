"""A schedule changed from Settings is told to its bot's chat once, and starts no turn there."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest

from harness.bots import ASSISTANT_ID, MENTION_TURN_ORDER, GroupService
from harness.llm import AssistantMessage, Message, StreamEvent, ToolMessage, UserMessage
from harness.prompts import SCHEDULE_CHANGE
from harness.runs.service import RunService
from harness.schedules import Schedule, ScheduleService
from harness.session.models import ScheduleChange, ScheduleChangeEvent, ToolCallEvent, TurnStart
from harness.session.repository import SessionNotFoundError
from harness.session.service import SessionService
from harness.tools.native.schedule import schedule_edit_tool
from tests.integration.web_helpers import send, settle
from tests.unit.fakes import SteppedClient, calls_tool, completed, gated_tool
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.unit.schedule_helpers import START, Clock, schedules_in
from tests.webapp import a_model_saved_in, bots_in, web_app

DAILY = "DTSTART:20990101T090000Z\nRRULE:FREQ=DAILY"
TITLE = 'Check "the deployment" — every morning'


Scripts = Callable[[str], Sequence[Sequence[StreamEvent]]]


@dataclass(frozen=True)
class Page:
    client: httpx.AsyncClient
    schedules: ScheduleService
    sessions: SessionService
    runs: RunService
    model: SteppedClient
    release: asyncio.Event
    made: Schedule


def _replying(text: str) -> Scripts:
    return lambda _: [completed(text)]


@pytest.fixture
async def page_of(tmp_path: Path) -> AsyncIterator[Callable[..., Awaitable[Page]]]:
    pages: list[Page] = []

    async def make(scripts: Scripts, bot_id: str = ASSISTANT_ID) -> Page:
        release = asyncio.Event()
        sessions = durable_service(tmp_path / "sessions")
        bots = bots_in(tmp_path, sessions)
        await bots.active_bots()
        schedules = schedules_in(tmp_path, Clock(START))
        made = schedules.create(bot_id, TITLE, "Check it.", DAILY)
        model = SteppedClient(*scripts(made.id))
        edit = schedule_edit_tool(GroupService(bots, sessions, MENTION_TURN_ORDER), schedules)
        runs = run_service(sessions, model, gated_tool(release), edit, bots=bots)
        app = web_app(
            tmp_path,
            sessions,
            runs,
            skills=no_skills(),
            bots=bots,
            secrets=a_model_saved_in(tmp_path),
            schedules=schedules,
        )
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://harness.test"
        )
        page = Page(client, schedules, sessions, runs, model, release, made)
        pages.append(page)
        return page

    yield make
    for page in pages:
        page.release.set()
        await settle(page.runs, ASSISTANT_ID)
        await page.client.aclose()


def _note(change: str, schedule_id: str) -> str:
    return SCHEDULE_CHANGE.format(
        change=change,
        schedule_id_json=json.dumps(schedule_id, ensure_ascii=False),
        schedule_title_json=json.dumps(TITLE, ensure_ascii=False),
    )


def _times_told(messages: list[Message], note: str) -> int:
    return sum(1 for m in messages if isinstance(m, UserMessage) and m.content == note)


async def _changes(page: Page) -> list[ScheduleChange]:
    events = (await page.sessions.read(ASSISTANT_ID)).events()
    return [e.change for e in events if isinstance(e, ScheduleChangeEvent)]


async def _turns(page: Page) -> int:
    events = (await page.sessions.read(ASSISTANT_ID)).events()
    return sum(1 for e in events if isinstance(e, TurnStart))


async def _answered(page: Page, prompt: str) -> None:
    await send(page.client, ASSISTANT_ID, prompt)
    await settle(page.runs, ASSISTANT_ID)


async def test_a_pause_from_the_page_is_told_once_in_the_next_request(page_of) -> None:
    page = await page_of(_replying("Noted."))

    paused = await page.client.post(f"/api/schedules/{page.made.id}/pause")

    assert paused.status_code == 204, paused.text
    told = ScheduleChange(schedule_id=page.made.id, title=TITLE, change="updated")
    assert await _changes(page) == [told]
    assert await _turns(page) == 0
    await _answered(page, "Hi")
    assert _times_told(page.model.seen_per_call[0], _note("updated", page.made.id)) == 1
    assert await _turns(page) == 1


async def test_a_resume_from_the_page_is_logged_as_updated(page_of) -> None:
    page = await page_of(_replying("Noted."))
    page.schedules.pause(page.made.id)

    resumed = await page.client.post(f"/api/schedules/{page.made.id}/resume")

    assert resumed.status_code == 204, resumed.text
    assert [c.change for c in await _changes(page)] == ["updated"]


async def test_a_delete_from_the_page_is_logged_as_deleted(page_of) -> None:
    page = await page_of(_replying("Noted."))

    deleted = await page.client.delete(f"/api/schedules/{page.made.id}")

    assert deleted.status_code == 204, deleted.text
    told = ScheduleChange(schedule_id=page.made.id, title=TITLE, change="deleted")
    assert await _changes(page) == [told]
    assert await _turns(page) == 0


async def test_run_now_from_the_page_logs_no_change(page_of) -> None:
    page = await page_of(_replying("Done."))

    ran = await page.client.post(f"/api/schedules/{page.made.id}/run")

    assert ran.status_code == 204, ran.text
    async with asyncio.timeout(5):
        while not page.schedules.get(page.made.id).deliveries:
            await asyncio.sleep(0.01)
    await settle(page.runs, ASSISTANT_ID)
    assert await _changes(page) == []


def _pausing(schedule_id: str) -> Sequence[Sequence[StreamEvent]]:
    arguments = json.dumps({"action": "update", "id": schedule_id, "active": False})
    return [calls_tool("schedule_edit", arguments), completed("Paused.")]


async def test_a_pause_through_schedule_edit_in_the_chat_logs_no_change(page_of) -> None:
    page = await page_of(_pausing)

    await _answered(page, "Pause it.")

    assert page.schedules.get(page.made.id).status == "paused"
    assert await _changes(page) == []


def _gated(_: str) -> Sequence[Sequence[StreamEvent]]:
    return [calls_tool("gate", '{"value": "x"}'), completed("Done.")]


async def test_a_change_while_a_turn_runs_is_seen_at_that_turns_next_request(page_of) -> None:
    page = await page_of(_gated)
    await send(page.client, ASSISTANT_ID, "Go.")
    await _gate_called(page)

    paused = await page.client.post(f"/api/schedules/{page.made.id}/pause")
    page.release.set()
    await settle(page.runs, ASSISTANT_ID)

    assert paused.status_code == 204, paused.text
    note = _note("updated", page.made.id)
    first, second = page.model.seen_per_call
    assert _times_told(first, note) == 0
    assert _times_told(second, note) == 1
    assert [type(m) for m in second[-3:]] == [AssistantMessage, ToolMessage, UserMessage]
    assert await _turns(page) == 1


async def test_a_change_to_a_bot_with_no_chat_logs_nothing(page_of) -> None:
    page = await page_of(_replying("Noted."), bot_id="gone")

    paused = await page.client.post(f"/api/schedules/{page.made.id}/pause")
    deleted = await page.client.delete(f"/api/schedules/{page.made.id}")

    assert (paused.status_code, deleted.status_code) == (204, 204)
    with pytest.raises(SessionNotFoundError):
        await page.sessions.read("gone")


async def _gate_called(page: Page) -> None:
    async with asyncio.timeout(5):
        while True:
            run = page.runs.active(ASSISTANT_ID)
            if run is not None and any(isinstance(e, ToolCallEvent) for e in run.session.events()):
                return
            await asyncio.sleep(0.01)
