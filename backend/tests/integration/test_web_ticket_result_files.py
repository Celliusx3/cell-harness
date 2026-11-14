"""A worker is told where the person's files go; the bot hears which of its files reach them."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from harness.bots import ASSISTANT_ID
from harness.session.domain.models import UserMessageEvent
from harness.tools.native.tickets import TICKET_REPORT, TICKET_ROUTE
from tests.integration.ticket_helpers import WORKER_START, ticketing_app
from tests.integration.web_helpers import ASSISTANT_START, of_type, once_said, send
from tests.unit.fakes import calls_tool, completed
from tests.webapp import files_in

ACCEPTED = json.dumps(
    {"items": [{"kind": "accept", "title": "Download the chapter", "task": "Download it."}]}
)
UNREACHABLE = "/home/pc/Jewel-Witch-Chapter-46-Raw.cbz"


async def _bytes(data: bytes) -> AsyncIterator[bytes]:
    yield data


def _scripts(summary: str) -> dict:
    return {
        WORKER_START: [
            calls_tool(TICKET_REPORT, json.dumps({"state": "ready", "summary": summary}), id="r1"),
            completed("Reported."),
        ],
        ASSISTANT_START: [
            calls_tool(TICKET_ROUTE, ACCEPTED, id="c1"),
            completed("On it."),
            completed("Here it is."),
        ],
    }


async def _report_text(tmp_path, summary: str) -> str:
    world = ticketing_app(tmp_path, _scripts(summary))
    async with world.client as client:
        await send(client, ASSISTANT_ID, "download the chapter")
        log = await once_said(client, ASSISTANT_ID, "Here it is.")
    (report,) = of_type(log, "ticket/report")
    return report["report"]["text"]


async def test_a_worker_is_told_the_folder_the_person_can_get_files_from(tmp_path) -> None:
    world = ticketing_app(tmp_path, _scripts("Done."))
    async with world.client as client:
        await send(client, ASSISTANT_ID, "download the chapter")
        await once_said(client, ASSISTANT_ID, "Here it is.")
        (row,) = (await client.get("/api/tickets", params={"bot_id": ASSISTANT_ID})).json()

    events = await world.tickets.worker_events(row["id"])
    first = next(e for e in events if isinstance(e, UserMessageEvent))
    folder = (tmp_path / "files" / ASSISTANT_ID).resolve()
    assert str(folder) in first.message.content


async def test_a_ready_report_s_file_in_the_chat_is_to_be_handed_over(tmp_path) -> None:
    saved = await files_in(tmp_path).save(ASSISTANT_ID, "chapter.cbz", _bytes(b"pages"))

    text = await _report_text(tmp_path, f"Saved the chapter as {saved.path}.")

    assert "send_file" in text
    assert saved.path in text.split("send_file", 1)[1]


async def test_a_ready_report_s_file_outside_the_chat_is_said_to_be_out_of_reach(tmp_path) -> None:
    text = await _report_text(tmp_path, f"The chapter is in your home folder: {UNREACHABLE}")

    assert "cannot get" in text
    assert UNREACHABLE in text.split("cannot get", 1)[1]
