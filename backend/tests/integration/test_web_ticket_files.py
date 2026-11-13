"""A worker's files and images are served on its ticket's page, and nothing outside them is."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import AsyncIterator

from harness.bots import ASSISTANT_ID
from harness.files import ChatFile
from harness.llm import ToolMessage
from harness.session.models import ToolResultEvent
from harness.tickets.service.worker import worker_session_id
from harness.tools.domain.outcome import ReturnedImage
from harness.tools.native.tickets import TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, Ticketing, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, once_said, send
from tests.mcp_stub import DOT_PNG
from tests.unit.fakes import calls_tool, completed
from tests.webapp import files_in, images_in

DOT = base64.b64decode(DOT_PNG)
DOT_SHA256 = hashlib.sha256(DOT).hexdigest()
ACCEPTED = json.dumps(
    {"items": [{"kind": "accept", "title": "Write the report", "task": "Write it."}]}
)
SCRIPTS = {
    WORKER_START: [completed("Report written.")],
    ASSISTANT_START: [
        calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
        completed("On it."),
        completed("The report is ready."),
    ],
}


async def _bytes(data: bytes) -> AsyncIterator[bytes]:
    yield data


async def _done_ticket(world: Ticketing) -> str:
    await send(world.client, ASSISTANT_ID, "write the report")
    await once_said(world.client, ASSISTANT_ID, "The report is ready.")
    (row,) = (await world.client.get("/api/tickets", params={"bot_id": ASSISTANT_ID})).json()
    return row["id"]


async def _saved(tmp_path, chat_id: str) -> ChatFile:
    return await files_in(tmp_path).save(chat_id, "report.txt", _bytes(b"the report"))


async def test_a_file_in_the_workers_folder_is_served_on_its_ticket(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        ticket_id = await _done_ticket(world)
        stored = await _saved(tmp_path, worker_session_id(ticket_id))
        served = await client.get(f"/api/tickets/{ticket_id}/file", params={"path": stored.path})

    assert served.status_code == 200
    assert served.content == b"the report"
    assert served.headers["x-content-type-options"] == "nosniff"


async def test_a_file_in_the_bots_own_folder_is_not_served_on_a_ticket(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        ticket_id = await _done_ticket(world)
        stored = await _saved(tmp_path, ASSISTANT_ID)
        served = await client.get(f"/api/tickets/{ticket_id}/file", params={"path": stored.path})

    assert served.status_code == 404


async def test_an_image_the_workers_log_shows_is_served_on_its_ticket(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        ticket_id = await _done_ticket(world)
        blocks = images_in(tmp_path).of_result((ReturnedImage(media_type="image/png", data=DOT),))
        session = await world.worker_logs.resume(worker_session_id(ticket_id))
        result = ToolMessage(tool_call_id="shot", content=blocks)
        session.append(ToolResultEvent(turn=0, step=0, message=result))
        await world.worker_logs.flush(session)
        served = await client.get(f"/api/tickets/{ticket_id}/images/{DOT_SHA256}")

    assert served.status_code == 200
    assert served.content == DOT
    assert served.headers["content-disposition"].startswith("inline")


async def test_an_image_the_workers_log_does_not_show_is_not_served(tmp_path) -> None:
    world = ticketing_app(tmp_path, SCRIPTS)
    async with world.client as client:
        ticket_id = await _done_ticket(world)
        images_in(tmp_path).of_result((ReturnedImage(media_type="image/png", data=DOT),))
        served = await client.get(f"/api/tickets/{ticket_id}/images/{DOT_SHA256}")

    assert served.status_code == 404
