"""Settings → Schedules over HTTP: list, pause, resume, run now and delete a bot's schedules."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from harness.bots import ASSISTANT_ID
from harness.bots.models import ASSISTANT_NAME
from harness.runs.service import RunService
from harness.schedules import ScheduleService
from tests.integration.web_helpers import settle
from tests.unit.fakes import SteppedClient, calls_tool, completed, gated_tool
from tests.unit.helpers import durable_service, no_skills, run_service
from tests.unit.schedule_helpers import START, Clock, schedules_in
from tests.webapp import a_model_saved_in, bots_in, web_app

DAILY = "DTSTART:20990101T090000Z\nRRULE:FREQ=DAILY"
SOONER = "DTSTART:20980101T090000Z\nRRULE:FREQ=DAILY"
ONCE_IN_DECEMBER = "DTSTART:20261201T090000Z\nRRULE:FREQ=DAILY;COUNT=1"
UNKNOWN = "no-such-schedule"
BUSY = "This schedule's bot is already running it."


@dataclass(frozen=True)
class Page:
    client: httpx.AsyncClient
    schedules: ScheduleService
    clock: Clock
    runs: RunService
    release: asyncio.Event


@pytest.fixture
async def page(tmp_path: Path) -> AsyncIterator[Page]:
    release = asyncio.Event()
    model = SteppedClient(calls_tool("gate", '{"value": "x"}'), completed("Done."))
    service = durable_service(tmp_path / "sessions")
    bots = bots_in(tmp_path, service)
    await bots.active_bots()
    runs = run_service(service, model, gated_tool(release), bots=bots)
    clock = Clock(START)
    schedules = schedules_in(tmp_path, clock)
    app = web_app(
        tmp_path,
        service,
        runs,
        skills=no_skills(),
        bots=bots,
        secrets=a_model_saved_in(tmp_path),
        schedules=schedules,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://harness.test") as client:
        yield Page(client, schedules, clock, runs, release)
        release.set()
        await settle(runs, ASSISTANT_ID)


async def _listed(page: Page) -> list[dict]:
    answered = await page.client.get("/api/schedules")
    assert answered.status_code == 200, answered.text
    return answered.json()


async def _delivered(page: Page, schedule_id: str) -> None:
    async with asyncio.timeout(5):
        while not page.schedules.get(schedule_id).deliveries:
            await asyncio.sleep(0.01)


async def test_the_list_puts_active_first_by_next_time_then_the_rest_newest_first(
    page: Page,
) -> None:
    paused = page.schedules.create(ASSISTANT_ID, "Paused", "P.", DAILY)
    page.schedules.pause(paused.id)
    page.clock.advance(timedelta(minutes=1))
    page.schedules.create(ASSISTANT_ID, "Later", "L.", DAILY)
    page.clock.advance(timedelta(minutes=1))
    sooner = page.schedules.create("gone", "Sooner", "Check the deployment.", SOONER)
    page.clock.advance(timedelta(minutes=1))
    ended = page.schedules.create(ASSISTANT_ID, "Ended", "E.", DAILY)
    page.schedules.end(ended.id)

    listed = await _listed(page)

    assert [row["title"] for row in listed] == ["Sooner", "Later", "Ended", "Paused"]
    assert [row["bot_name"] for row in listed] == ["gone", *[ASSISTANT_NAME] * 3]
    assert listed[0] == {
        "id": sooner.id,
        "bot_id": "gone",
        "bot_name": "gone",
        "title": "Sooner",
        "prompt": "Check the deployment.",
        "rrule": SOONER,
        "status": "active",
        "scheduled_at": "2098-01-01T09:00:00Z",
        "last_occurrence_at": None,
        "created_at": "2026-11-12T08:02:00Z",
    }


async def test_a_paused_schedule_resumes(page: Page) -> None:
    made = page.schedules.create(ASSISTANT_ID, "Daily", "D.", DAILY)

    paused = await page.client.post(f"/api/schedules/{made.id}/pause")
    assert paused.status_code == 204, paused.text
    assert [row["status"] for row in await _listed(page)] == ["paused"]

    resumed = await page.client.post(f"/api/schedules/{made.id}/resume")
    assert resumed.status_code == 204, resumed.text
    assert [row["status"] for row in await _listed(page)] == ["active"]


async def test_run_now_delivers_once_and_leaves_the_next_time(page: Page) -> None:
    made = page.schedules.create(ASSISTANT_ID, "Daily", "D.", DAILY)

    ran = await page.client.post(f"/api/schedules/{made.id}/run")
    assert ran.status_code == 204, ran.text
    await _delivered(page, made.id)
    page.release.set()
    await settle(page.runs, ASSISTANT_ID)

    (row,) = await _listed(page)
    assert row["scheduled_at"] == "2099-01-01T09:00:00Z"
    assert row["status"] == "active"
    assert row["last_occurrence_at"] is not None
    assert len(page.schedules.get(made.id).deliveries) == 1


async def test_run_now_while_its_chat_runs_one_is_refused(page: Page) -> None:
    made = page.schedules.create(ASSISTANT_ID, "Daily", "D.", DAILY)
    assert (await page.client.post(f"/api/schedules/{made.id}/run")).status_code == 204

    again = await page.client.post(f"/api/schedules/{made.id}/run")

    assert again.status_code == 409
    assert again.json() == {"detail": BUSY}


async def test_a_deleted_schedule_leaves_the_list(page: Page) -> None:
    made = page.schedules.create(ASSISTANT_ID, "Daily", "D.", DAILY)

    deleted = await page.client.delete(f"/api/schedules/{made.id}")

    assert deleted.status_code == 204
    assert await _listed(page) == []


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", f"/api/schedules/{UNKNOWN}/pause"),
        ("POST", f"/api/schedules/{UNKNOWN}/resume"),
        ("POST", f"/api/schedules/{UNKNOWN}/run"),
        ("DELETE", f"/api/schedules/{UNKNOWN}"),
    ],
)
async def test_an_unknown_schedule_is_not_found(page: Page, method: str, path: str) -> None:
    answered = await page.client.request(method, path)

    assert answered.status_code == 404
    assert UNKNOWN in answered.json()["detail"]


async def test_resuming_a_schedule_with_no_time_left_is_refused(page: Page) -> None:
    made = page.schedules.create(ASSISTANT_ID, "Once", "O.", ONCE_IN_DECEMBER)
    page.schedules.pause(made.id)
    page.clock.advance(timedelta(days=30))

    answered = await page.client.post(f"/api/schedules/{made.id}/resume")

    assert answered.status_code == 422
    assert answered.json() == {"detail": "rrule: no occurrence after now"}
